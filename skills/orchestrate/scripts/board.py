#!/usr/bin/env python3
"""Project board for a multi-session Claude Code build.

One JSON file per project (<docs>/state.json) is the source of truth. Every write takes a
file lock, replaces the JSON atomically and re-renders STATUS.md next to it, so several
sessions can update the board at once. The Conductor app reads the same JSON, found via
~/.conductor/projects.json.

Task states: todo -> assigned (START sent) -> progress -> qa -> done | fail, plus blocked.
Only `qa --verdict pass` on the submitted commit marks a task done.

Stdlib only. `board.py --help`, `board.py <command> --help`.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:                      # macOS / Linux
    import fcntl
    msvcrt = None
except ImportError:       # Windows
    fcntl = None
    import msvcrt

WINDOWS = os.name == "nt"

TASK_STATES = ["todo", "assigned", "progress", "qa", "fail", "blocked", "done"]
BUSY_STATES = ("assigned", "progress", "fail")          # a lane with one of these gets no new START
SESSION_STATES = ["working", "idle", "stopped", "quiet", "gone"]
REGISTRY = os.environ.get("CONDUCTOR_REGISTRY") or os.path.expanduser("~/.conductor/projects.json")  # env: tests/evals only
NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.sh")
MAX_EVENTS = 300
STALE_MIN = 60       # no task/session activity for this long -> ask for a status line
QA_NUDGE_MIN = 15
BREAKER_FAILS = 3    # a task's 3rd FAIL: the orchestrator must change the approach, not resend
# Why a QA FAIL happened (one or more per verdict), so runs can be compared over time:
FAIL_CLASSES = ["defect", "missed", "evidence", "regression", "plan", "process", "env", "other"]


def now():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse(iso):
    try:
        return dt.datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def age_min(iso):
    t = parse(iso)
    if not t:
        return None
    return int((dt.datetime.now().astimezone() - t).total_seconds() // 60)


def fmt_age(m):
    if m is None:
        return "-"
    if m < 60:
        return f"{m}m"
    if m < 1440:
        return f"{m // 60}h{m % 60:02d}m"
    return f"{m // 1440}d"


def die(msg):
    print(f"board: {msg}", file=sys.stderr)
    sys.exit(2)


def csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SAFE_REF = re.compile(r"^[^<>\"'&`\x00-\x1f]{1,500}$")  # a sha, or "p:ab12,k:cd34", "ghl:<id>@v6", "file:out.csv"


def check_args(a):
    """Ids, names and commits end up in STATUS.md and the Conductor page: ids are plain tokens, commit refs
    carry no HTML characters."""
    for k in ("id", "name", "lane", "by", "session"):
        if k == "name" and a.f is cmd_init:  # init --name is the display name, free text
            continue
        v = getattr(a, k, None)
        if isinstance(v, str) and v and not SAFE_ID.match(v):
            die(f"--{k} {v!r}: use letters, digits, dot, dash or underscore (max 64)")
    for k in ("commit", "sha"):
        v = getattr(a, k, None)
        if isinstance(v, str) and v and not SAFE_REF.match(v):
            die(f"--{k} {v!r}: no < > \" ' & ` or control characters, max 500")
    for w in csv(getattr(a, "waits", None) or "") if isinstance(getattr(a, "waits", None), str) else []:
        if not SAFE_ID.match(w):
            die(f"--waits {w!r}: not a task id")
    for pair in getattr(a, "pairs", None) or []:
        name = pair.partition("=")[0]
        if not SAFE_ID.match(name):
            die(f"session name {name!r}: use letters, digits, dot, dash or underscore")



# ---------- portability (macOS, Linux, Windows) ----------

def lock_file(f, exclusive=True, block=True):
    """Advisory lock on an open file. Windows has no shared locks: readers lock exclusively there.
    Raises BlockingIOError when block=False and someone else holds it."""
    if fcntl:
        fcntl.flock(f, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | (0 if block else fcntl.LOCK_NB))
        return
    f.seek(0)
    while True:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            if not block:
                raise BlockingIOError("locked")
            time.sleep(0.05)


def unlock_file(f):
    if fcntl:
        fcntl.flock(f, fcntl.LOCK_UN)
        return
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def replace_file(src, dst):
    """os.replace, retried on Windows while another process (Conductor) has dst open for reading."""
    for i in range(100):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if not WINDOWS or i == 99:
                raise
            time.sleep(0.02)


def pid_alive(pid):
    """True if the process exists. Never signals it (os.kill(pid, 0) on Windows sends Ctrl+C)."""
    if not pid or pid <= 0:
        return False
    if WINDOWS:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259     # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def shell_script_cmd(path):
    """How to run a .sh file: directly on macOS/Linux, through Git Bash on Windows."""
    if not WINDOWS:
        return [path]
    for b in (os.path.expandvars(r"%ProgramFiles%\Git\bin\bash.exe"), os.path.expandvars(r"%ProgramFiles(x86)%\Git\bin\bash.exe"),
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"), shutil.which("bash")):
        if b and os.path.isfile(b) and "system32" not in b.lower():   # System32\bash.exe is WSL, not Git Bash
            return [b, path]
    return None


# ---------- storage ----------

def state_path(docs):
    return os.path.join(os.path.abspath(docs), "state.json")


def save(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".state.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o644)
    replace_file(tmp, path)


class Board:
    """Lock, load, yield the state; on a clean exit save it and re-render STATUS.md."""

    def __init__(self, docs, write=True):
        self.docs = os.path.abspath(docs)
        self.path = state_path(docs)
        self.write = write

    def __enter__(self):
        if not os.path.exists(self.path):
            die(f"no state.json in {self.docs} (run `board.py init` first)")
        self.lockf = open(self.path + ".lock", "w", encoding="utf-8")
        lock_file(self.lockf, exclusive=self.write)
        with open(self.path, encoding="utf-8") as f:
            self.state = json.load(f)
        return self.state

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None and self.write:
                self.state["updatedAt"] = now()
                save(self.path, self.state)
                render(self.docs, self.state)
        finally:
            unlock_file(self.lockf)
            self.lockf.close()
        return False


def event(state, who, text):
    state.setdefault("events", []).append({"at": now(), "who": who or "?", "text": text})
    state["events"] = state["events"][-MAX_EVENTS:]


def find(items, key, value):
    return next((it for it in items if it.get(key) == value), None)


def need_task(state, tid):
    t = find(state["tasks"], "id", tid)
    if not t:
        die(f"unknown task {tid}")
    return t


# ---------- registry ----------

def register(state, docs):
    os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
    with open(REGISTRY + ".lock", "w", encoding="utf-8") as lockf:
        lock_file(lockf)
        reg = {"version": 1, "projects": []}
        if os.path.exists(REGISTRY):
            with open(REGISTRY, encoding="utf-8") as f:
                reg = json.load(f)
        sp = state_path(docs)
        reg["projects"] = [p for p in reg.get("projects", []) if p.get("state") != sp]
        reg["projects"].append({"id": state["id"], "name": state["name"], "state": sp, "addedAt": now()})
        save(REGISTRY, reg)


# ---------- derived views ----------

def stats(state):
    """Counts for REQUIRED tasks only: optional tasks never move progress or "all done"."""
    by = {s: 0 for s in TASK_STATES}
    req = [t for t in state["tasks"] if not t.get("optional")]
    for t in req:
        by[t["state"]] = by.get(t["state"], 0) + 1
    total = len(req)
    return by, total, (round(100 * by["done"] / total) if total else 0)


def optional_tasks(state):
    return [t for t in state["tasks"] if t.get("optional")]


def opt_line(state):
    o = optional_tasks(state)
    return f" (+{len(o)} optional, {sum(t['state'] == 'done' for t in o)} done)" if o else ""


def open_waiting(state):
    return [w for w in state.get("waiting", []) if not w.get("answer")]


def lane_session(state, lane):
    if lane == "orchestrator":     # the user-only / gate tasks belong to the orchestrator
        return next((s for s in state.get("sessions", []) if s.get("role") == "orchestrator"), None)
    return next((s for s in state.get("sessions", []) if s.get("lane") == lane), None)


def lane_name(state, lane):
    s = lane_session(state, lane)
    return s["name"] if s else lane


def ready(state):
    """First startable task per lane: todo, deps done, not held by an open question,
    and the lane has nothing assigned / in progress / failed."""
    done = {t["id"] for t in state["tasks"] if t["state"] == "done"}
    held = {b for w in open_waiting(state) for b in w.get("blocks", [])}
    busy = {t["lane"] for t in state["tasks"] if t["state"] in BUSY_STATES}
    out, seen = [], set()
    for t in sorted(state["tasks"], key=lambda x: bool(x.get("optional"))):  # required first, plan order kept
        if t["lane"] in busy or t["lane"] in seen:
            continue
        if t["state"] == "todo" and t["id"] not in held and all(w in done for w in t.get("waits", [])):
            out.append(t)
            seen.add(t["lane"])
    return out


def last_activity(state, t):
    """Newest of: task update, lane session seen / last commit / last message."""
    stamps = [t.get("updatedAt")]
    s = lane_session(state, t["lane"])
    if s:
        stamps += [s.get("seen"), (s.get("lastCommit") or {}).get("at"), (s.get("lastMessage") or {}).get("at")]
    ts = [parse(x) for x in stamps if parse(x)]
    return max(ts).isoformat() if ts else None


def next_id(state, prefix):
    n = 0
    for w in state.get("waiting", []):
        wid = w.get("id", "")
        if wid.startswith(prefix) and wid[len(prefix):].isdigit():
            n = max(n, int(wid[len(prefix):]))
    return f"{prefix}{n + 1}"


# ---------- render STATUS.md ----------

def render(docs, state):
    by, total, pct = stats(state)
    L = [f"# {state['name']}: status board", "",
         "Generated by board.py from state.json. Do not edit by hand. Ages are as of the last write.",
         f"Updated {state.get('updatedAt', '-')}.", "",
         f"**{pct}% done**: {by['done']} of {total} required tasks{opt_line(state)}. Assigned {by['assigned']}, in progress {by['progress']}, "
         f"ready for QA {by['qa']}, QA failed {by['fail']}, blocked {by['blocked']}, to do {by['todo']}."]
    hb = state.get("heartbeat") or {}
    if hb:
        L.append(f"Orchestrator heartbeat: {hb.get('at')}.")
    if state.get("gates"):
        L.append("Gates (only the user opens): " + "; ".join(state["gates"]) + ".")
    L += ["", "## Waiting on you", ""]
    ow = open_waiting(state)
    for w in ow:
        L.append(f"- **{w['id']}** ({w.get('kind', 'decision')}) {w['question']}"
                 + (f" Options: {' / '.join(w['options'])}." if w.get("options") else "")
                 + (f" Recommended: {w['recommendation']}." if w.get("recommendation") else "")
                 + (f" Blocks: {', '.join(w['blocks'])}." if w.get("blocks") else "")
                 + f" Asked {w.get('askedAt')}.")
    if not ow:
        L.append("Nothing.")
    L += ["", "## Tasks", "", "| Task | Title | Lane | State | Waits for | Commit | QA | Updated |", "|---|---|---|---|---|---|---|---|"]
    for t in state["tasks"]:
        qa = t.get("qa") or {}
        qa_s = f"{qa.get('verdict', '').upper()} {qa.get('sha', '')}".strip() if qa else "-"
        L.append(f"| {t['id']} | {t['title']}{' (optional)' if t.get('optional') else ''} | {t['lane']} | {t['state']} | {', '.join(t.get('waits', [])) or '-'} "
                 f"| {t.get('commit') or '-'} | {qa_s} | {t.get('updatedAt', '-')} |")
    L += ["", "## Sessions", "", "| Session | Role | Lane | State | Doing now | Last seen | Last commit |", "|---|---|---|---|---|---|---|"]
    for s in state.get("sessions", []):
        lc = s.get("lastCommit") or {}
        L.append(f"| {s['name']} | {s.get('role', '-')} | {s.get('lane') or '-'} | {s.get('state', '-')} | {s.get('doing') or '-'} "
                 f"| {s.get('seen') or 'never'} | {(lc.get('sha', '') + ' ' + lc.get('msg', '')).strip() or '-'} |")
    L += ["", "## Recent events", ""]
    L += [f"- {e['at']} · {e['who']} · {e['text']}" for e in state.get("events", [])[-15:][::-1]]
    L.append("")
    tmp = os.path.join(docs, ".STATUS.md.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    replace_file(tmp, os.path.join(docs, "STATUS.md"))


# ---------- commands ----------

def cmd_init(a):
    docs = os.path.abspath(a.docs)
    os.makedirs(os.path.join(docs, "lanes"), exist_ok=True)
    p = state_path(docs)
    if os.path.exists(p) and not a.force:
        with open(p, encoding="utf-8") as f:
            register(json.load(f), docs)
        print(f"exists: {p} (registered again; --force resets it)")
        return
    st = {"version": 1, "id": a.id, "name": a.name, "docs": docs,
          "code": os.path.abspath(a.code) if a.code else None,
          "phase": a.phase or "", "target": a.target or "", "createdAt": now(), "updatedAt": now(),
          "heartbeat": None, "gates": [g.strip() for g in (a.gates or "").split(";") if g.strip()],
          "lanes": [], "sessions": [], "tasks": [], "waiting": [], "events": []}
    event(st, "setup", "board created")
    save(p, st)
    render(docs, st)
    register(st, docs)
    print(f"created {p} and registered it in {REGISTRY}")


def cmd_lane(a):
    with Board(a.docs) as st:
        ln = find(st["lanes"], "id", a.id)
        if not ln:
            ln = {"id": a.id}
            st["lanes"].append(ln)
        ln["label"] = a.label or ln.get("label") or a.id
        if a.owns is not None:
            ln["owns"] = csv(a.owns)
        print(f"lane {a.id} ok")


def cmd_task_add(a):
    with Board(a.docs) as st:
        t = find(st["tasks"], "id", a.id)
        if t and not a.update:
            die(f"task {a.id} exists (use --update)")
        if not t:
            t = {"id": a.id, "state": "todo", "commit": None, "qa": None, "waits": []}
            st["tasks"].append(t)
            event(st, a.by or "setup", f"task {a.id} added")
        t["title"] = a.title or t.get("title", a.id)
        t["lane"] = a.lane or t.get("lane", "")
        if a.waits is not None:
            t["waits"] = csv(a.waits)
        if a.optional:
            t["optional"] = True
        t["updatedAt"] = now()
        print(f"task {a.id} ok" + (" (optional)" if t.get("optional") else ""))


def cmd_task(a):
    with Board(a.docs) as st:
        t = need_task(st, a.id)
        if a.state and a.state != t["state"]:
            if a.state == "done" and not a.force and not (t["lane"] == "orchestrator" and a.note):
                die("only `board.py qa <id> --verdict pass --sha <submitted sha>` marks a task done "
                    "(a gate task on the orchestrator lane: --state done --note \"The user said go at ...; result\")")
            if t["state"] == "done" and not a.force:
                die(f"{a.id} is done; reopening needs --force and a reason in --note")
            t["state"] = a.state
        if a.commit:
            t["commit"] = a.commit
        flip = ""
        if a.optional and not t.get("optional"):
            t["optional"], flip = True, "marked optional"
            deps = [x["id"] for x in st["tasks"] if a.id in x.get("waits", []) and not x.get("optional") and x["state"] != "done"]
            if deps:
                print(f"note: required task(s) {', '.join(deps)} wait on {a.id}; they stay held until it is done "
                      f"or their waits change (task-add <id> --update --waits ...)")
        elif a.required and t.get("optional"):
            t.pop("optional"); flip = "marked required"
        t["updatedAt"] = now()
        if a.note:
            t["note"] = a.note
        if flip:
            event(st, a.by, f"{a.id} {flip}" + (f": {a.note}" if a.note else ""))
            if not a.state and not a.commit:
                print(f"{a.id} {flip}")
                return
        event(st, a.by, f"{a.id} {t['state']}" + (f" @ {a.commit}" if a.commit else "") + (f": {a.note}" if a.note else ""))
        print(f"{a.id} {t['state']}")


def cmd_qa(a):
    with Board(a.docs) as st:
        t = need_task(st, a.id)
        if t["state"] != "qa" and not a.force:
            die(f"{a.id} is {t['state']}, not qa: review only submitted tasks")
        c = t.get("commit") or ""
        if not a.force and not (c and (c.startswith(a.sha) or a.sha.startswith(c))):
            die(f"sha {a.sha} is not the submitted commit {c or '(none)'}; review the latest submission")
        classes = csv(a.classes)
        bad = [c for c in classes if c not in FAIL_CLASSES]
        if bad:
            die(f"unknown --classes {bad}; use: {', '.join(FAIL_CLASSES)}")
        if a.verdict == "fail" and not classes:   # optional so builds started on older SESSIONS.md keep working
            print(f"note: add --classes next time ({', '.join(FAIL_CLASSES)})", file=sys.stderr)
        t["qa"] = {"verdict": a.verdict, "sha": a.sha, "issues": a.issues, "at": now(), "by": a.by}
        if classes:
            t["qa"]["classes"] = classes
        t.setdefault("verdicts", []).append(dict(t["qa"]))
        t["state"] = "done" if a.verdict == "pass" else "fail"
        t["fails"] = t.get("fails", 0) + (a.verdict == "fail")
        t["updatedAt"] = now()
        event(st, a.by, f"{a.id} QA {a.verdict.upper()} @ {a.sha}" + (f" ({a.issues} issues: {','.join(classes)})" if a.issues else ""))
        msg = f"{a.id} {t['state']}" + (f" (fail #{t['fails']})" if a.verdict == "fail" else "")
        if a.verdict == "fail" and t["fails"] >= BREAKER_FAILS:
            msg += " BREAKER: the orchestrator changes the approach before another round (SESSIONS.md, Repeated failures)"
        print(msg)


def touch_session(s, a, stamp=True):
    for k in ("role", "lane", "doing", "note"):
        v = getattr(a, k, None)
        if v is not None:
            s[k] = v
    if getattr(a, "state", None):
        s["state"] = a.state
    if getattr(a, "commit", None):
        s["lastCommit"] = {"sha": a.commit, "msg": a.msg or "", "at": now()}
    elif getattr(a, "msg", None):
        s["lastMessage"] = {"text": a.msg, "at": now()}
    if getattr(a, "asked", False):
        s["askedAt"] = now()
    if stamp:
        s["seen"] = now()
        s.pop("askedAt", None)


def cmd_session(a):
    with Board(a.docs) as st:
        s = find(st["sessions"], "name", a.name)
        if not s:
            s = {"name": a.name, "state": "gone", "seen": None}
            st["sessions"].append(s)
        # A session reporting on itself bumps last-seen; the orchestrator marking others passes --no-seen.
        touch_session(s, a, stamp=not a.no_seen)
        print(f"session {a.name} {s['state']}")


def cmd_sync(a):
    """Orchestrator: record several sessions' states in one call: name=state[:doing] ..."""
    with Board(a.docs) as st:
        for pair in a.pairs:
            name, _, rest = pair.partition("=")
            state, _, doing = rest.partition(":")
            if state not in SESSION_STATES:
                die(f"{pair}: state must be one of {SESSION_STATES}")
            s = find(st["sessions"], "name", name)
            if not s:
                die(f"unknown session {name}")
            if s.get("state") != state:
                event(st, a.by, f"{name} {s.get('state')} -> {state}")
            s["state"] = state
            if doing:
                s["doing"] = doing
        print("synced " + ", ".join(a.pairs))


def cmd_ask(a):
    prefix = {"decision": "D", "gate": "G", "stuck": "S"}[a.kind]
    with Board(a.docs) as st:
        if a.kind == "stuck" and a.session:
            dup = next((w for w in open_waiting(st) if w.get("kind") == "stuck" and w.get("session") == a.session), None)
            if dup:
                print(f"already open: {dup['id']} for {a.session} (not pinging again)")
                sys.exit(3)
        wid = a.id or next_id(st, prefix)
        if find(st["waiting"], "id", wid):
            die(f"waiting item {wid} exists")
        st["waiting"].append({"id": wid, "kind": a.kind, "session": a.session, "question": a.question,
                              "options": [o.strip() for o in (a.options or "").split("|") if o.strip()],
                              "recommendation": a.recommend or "", "why": a.why or "",
                              "blocks": csv(a.blocks), "askedAt": now(), "answer": None, "answeredAt": None})
        event(st, a.by, f"waiting on you {wid}: {a.question}")
        print(wid)


def cmd_answer(a):
    with Board(a.docs) as st:
        w = find(st["waiting"], "id", a.id)
        if not w:
            die(f"unknown waiting item {a.id}")
        if w.get("answer"):
            die(f"{a.id} is already answered: {w['answer']}")
        if a.from_app and w.get("kind") == "gate":
            die("gates open only by the user typing go in the orchestrator session, not from the app")
        w["answer"] = a.answer
        w["answeredAt"] = now()
        w["answeredBy"] = "user-app" if a.from_app else (a.by or "orchestrator")
        w["pending"] = bool(a.from_app)      # the orchestrator still has to record and announce it
        event(st, w["answeredBy"], f"{a.id} answered: {a.answer}")
        print(f"{a.id} answered")


def cmd_ack(a):
    with Board(a.docs) as st:
        w = find(st["waiting"], "id", a.id)
        if not w:
            die(f"unknown waiting item {a.id}")
        w["pending"] = False
        event(st, a.by, f"{a.id} recorded and announced")
        print(f"{a.id} acknowledged")


def cmd_wait_answer(a):
    """Blocks until the user answers something in the Conductor app, prints it, exits 0. The
    orchestrator keeps this running in the background: its exit wakes the session within seconds,
    instead of the answer waiting for the next loop check. Each answer is reported once."""
    path = state_path(a.docs)
    last = None
    parent = os.getppid()
    while True:
        if os.getppid() == 1 or (WINDOWS and not pid_alive(parent)):   # the session that started this is gone
            sys.exit(4)
        try:
            m = os.stat(path).st_mtime
        except OSError:
            m = None
        if m != last:
            last = m
            with Board(a.docs, write=False) as st:
                fresh = [w for w in st.get("waiting", []) if w.get("pending") and not w.get("notified")]
            if fresh:
                with Board(a.docs) as st:
                    fresh = [w for w in st.get("waiting", []) if w.get("pending") and not w.get("notified")]
                    for w in fresh:
                        w["notified"] = now()
                if fresh:
                    print("ANSWERED IN APP (record, announce, then ack): " + "; ".join(f"{w['id']} -> {w['answer']}" for w in fresh))
                    return
        time.sleep(2)


def cmd_note(a):
    with Board(a.docs) as st:
        event(st, a.by, a.text)
        print("noted")


def cmd_heartbeat(a):
    with Board(a.docs) as st:
        st["heartbeat"] = {"at": now(), "by": a.by}
        if a.phase is not None:
            st["phase"] = a.phase
        print("heartbeat")


def cmd_summary(a):
    with Board(a.docs, write=False) as st:
        by, total, pct = stats(st)
        print(f"{st['name']}: {pct}% ({by['done']}/{total}){opt_line(st)} | assigned {by['assigned']} progress {by['progress']} "
              f"qa {by['qa']} fail {by['fail']} blocked {by['blocked']} todo {by['todo']}")
        r = ready(st)
        rs = [t for t in r if t["lane"] != "orchestrator"]
        gs = [t for t in r if t["lane"] == "orchestrator"]
        print("READY TO START (one per free lane): " + (", ".join(f"{t['id']}->{lane_name(st, t['lane'])}" for t in rs) or "none"))
        if gs:
            print("GATE READY (ask the user for go): " + ", ".join(f"{t['id']} {t['title']}" for t in gs))
        active = []
        for t in st["tasks"]:
            if t["state"] in ("assigned", "progress", "fail", "blocked"):
                la = last_activity(st, t)
                s = lane_session(st, t["lane"])
                flag = ""
                if t["state"] != "blocked" and (age_min(la) or 0) >= STALE_MIN:
                    flag = " STALE" + (f" (status asked {fmt_age(age_min(s.get('askedAt')))} ago)" if s and s.get("askedAt") else "")
                active.append(f"{t['id']} {t['state']} {lane_name(st, t['lane'])} last activity {fmt_age(age_min(la))}{flag}")
        print("ACTIVE: " + ("; ".join(active) or "none"))
        qa = [t for t in st["tasks"] if t["state"] == "qa"]
        print("QA QUEUE: " + (", ".join(f"{t['id']}@{t.get('commit')} {fmt_age(age_min(t.get('updatedAt')))}"
                                        + (" NUDGE" if (age_min(t.get("updatedAt")) or 0) >= QA_NUDGE_MIN else "") for t in qa) or "empty"))
        repeat = [t for t in st["tasks"] if t.get("fails", 0) >= 2 and t["state"] != "done"]
        if repeat:
            print("REPEATED QA FAILS: " + ", ".join(f"{t['id']} x{t['fails']}" + (" BREAKER" if t["fails"] >= BREAKER_FAILS else "")
                                                   for t in repeat))
        app = [w for w in st.get("waiting", []) if w.get("pending")]
        if app:
            print("ANSWERED IN APP (record, announce, then ack): " + "; ".join(f"{w['id']} -> {w['answer']}" for w in app))
        ow = open_waiting(st)
        print("WAITING ON YOU: " + (", ".join(f"{w['id']} ({w.get('kind')}) {fmt_age(age_min(w.get('askedAt')))}" for w in ow) or "none"))
        print("SESSIONS: " + (", ".join(f"{s['name']}={s.get('state')}" for s in st.get("sessions", [])) or "none"))
        print("NEXT IDS: " + " ".join(next_id(st, p) for p in "DGS"))
        if total and by["done"] == total:
            print("ALL TASKS DONE")
            oo = [x for x in optional_tasks(st) if x["state"] != "done"]
            if oo:
                print("OPTIONAL OPEN (don't count; ask the user once: finish them or wrap up): "
                      + ", ".join(f"{x['id']} {x['state']}" for x in oo))


def cmd_watchdog(a):
    """Run from cron/launchd: ping the user if the orchestrator heartbeat is older than --max-min."""
    with Board(a.docs, write=False) as st:
        hb = (st.get("heartbeat") or {}).get("at")
        name, sid = st["name"], st["id"]
        by, total, _ = stats(st)
    m = age_min(hb)
    if total and by["done"] == total:
        print("all done; nothing to watch")
        return
    if m is not None and m < a.max_min:
        print(f"ok: heartbeat {m}m ago")
        return
    flag = os.path.join(os.path.abspath(a.docs), ".watchdog-pinged")
    if os.path.exists(flag) and time.time() - os.path.getmtime(flag) < a.repeat_min * 60:
        print("stale, already pinged recently")
        return
    msg = (f"No orchestrator heartbeat for {fmt_age(m)}." if m is not None else "The orchestrator has never written a heartbeat.") + \
          f" Check the {sid}-orchestrator tab: its loop may have stopped (usage limit, closed tab, or expired loop)."
    runner = shell_script_cmd(NOTIFY)
    if runner:
        subprocess.run(runner + [f"{name} · orchestrator silent", msg])
    else:
        print("can't ping: Git Bash not found (notify.sh needs it on Windows)", file=sys.stderr)
    open(flag, "w", encoding="utf-8").close()


def run_stats(st):
    """Measured outcomes of one build, for comparing runs (old skill vs new)."""
    T = [t for t in st["tasks"] if t.get("lane") != "orchestrator"]
    reviewed = [t for t in T if t.get("qa") or t.get("fails")]
    first = [t for t in reviewed if t["state"] == "done" and not t.get("fails")]
    fails = [t.get("fails", 0) for t in reviewed]
    classes = {}
    for t in T:
        for v in t.get("verdicts", []):
            for c in v.get("classes", []):
                classes[c] = classes.get(c, 0) + 1
    W = st.get("waiting", [])
    kinds = {}
    for w in W:
        kinds[w.get("kind", "?")] = kinds.get(w.get("kind", "?"), 0) + 1
    waits = sorted(m for m in ((parse(w.get("answeredAt")) - parse(w.get("askedAt"))).total_seconds() / 60
                               for w in W if parse(w.get("askedAt")) and parse(w.get("answeredAt"))))
    t0, t1 = parse(st.get("createdAt")), parse(st.get("updatedAt"))
    return {"id": st.get("id"), "tasks": len(T), "reviewed": len(reviewed),
            "first_pass_yield": round(len(first) / len(reviewed), 2) if reviewed else None,
            "fails_per_reviewed": round(sum(fails) / len(reviewed), 2) if reviewed else None,
            "tasks_3plus_fails": sum(1 for f in fails if f >= BREAKER_FAILS), "max_fails": max(fails or [0]),
            "fail_classes": classes, "waiting": kinds,
            "median_wait_min": round(waits[len(waits) // 2]) if waits else None,
            "span_h": round((t1 - t0).total_seconds() / 3600, 1) if t0 and t1 else None}


def cmd_stats(a):
    """One build's numbers, or every registered build with --all (JSON lines with --json)."""
    rows = []
    if a.all:
        reg = json.load(open(REGISTRY, encoding="utf-8")) if os.path.exists(REGISTRY) else {}
        for p in reg.get("projects", []):
            if os.path.exists(p["state"]):
                rows.append(run_stats(json.load(open(p["state"], encoding="utf-8"))))
    else:
        with Board(a.docs, write=False) as st:
            rows.append(run_stats(st))
    for r in rows:
        if a.json:
            print(json.dumps(r))
            continue
        fpy = "-" if r["first_pass_yield"] is None else f"{round(100 * r['first_pass_yield'])}%"
        print(f"{r['id']}: {r['tasks']} tasks, {r['reviewed']} reviewed | first-pass {fpy} | "
              f"fails/task {r['fails_per_reviewed']} | 3+ fails {r['tasks_3plus_fails']} (max {r['max_fails']}) | "
              f"waiting {r['waiting'] or '{}'} median {r['median_wait_min']} min | "
              f"classes {r['fail_classes'] or '-'} | span {r['span_h']} h")


def cmd_run(a):
    """Run a command holding one of N slots of a named pool: `tests` (default) so lanes don't run
    full suites all at once, or a shared resource such as `browser` or `staging` (use --slots 1)."""
    if not a.cmd:
        die("usage: board.py run [--pool NAME] [--slots N] -- <command ...>")
    cmd = a.cmd[1:] if a.cmd[0] == "--" else a.cmd
    if WINDOWS and cmd and shutil.which(cmd[0]):
        cmd = [shutil.which(cmd[0])] + cmd[1:]
    docs = os.path.abspath(a.docs)
    pool = a.pool or "tests"
    if not pool.replace("-", "").isalnum():
        die("--pool takes letters, digits and dashes")
    waited = 0
    while True:
        for i in range(a.slots):
            f = open(os.path.join(docs, f".{pool}.{i}.lock"), "w", encoding="utf-8")
            try:
                lock_file(f, block=False)
            except BlockingIOError:
                f.close()
                continue
            try:
                if waited:
                    print(f"[board run] got a {pool} slot after {waited}s", file=sys.stderr)
                if a.cwd and not os.path.isdir(a.cwd):
                    die(f"--cwd {a.cwd} is not a folder")
                sys.exit(subprocess.call(cmd, cwd=a.cwd or None))
            finally:
                unlock_file(f)
                f.close()
        time.sleep(5)
        waited += 5


def cmd_render(a):
    with Board(a.docs):
        pass
    print("rendered")


def _nested(p, q):
    p, q = os.path.normpath(p).replace("\\", "/").rstrip("/"), os.path.normpath(q).replace("\\", "/").rstrip("/")
    return p == q or q.startswith(p + "/") or p.startswith(q + "/")


def cmd_validate(a):
    with Board(a.docs, write=False) as st:
        errs = []
        ids = [t["id"] for t in st["tasks"]]
        if len(ids) != len(set(ids)):
            errs.append("duplicate task ids")
        lanes = {l["id"] for l in st["lanes"]}
        for t in st["tasks"]:
            if t["state"] not in TASK_STATES:
                errs.append(f"{t['id']}: bad state {t['state']}")
            if t["lane"] not in lanes and not (t["lane"] == "orchestrator" and lane_session(st, "orchestrator")):
                errs.append(f"{t['id']}: unknown lane {t['lane']}")
            for w in t.get("waits", []):
                if w not in ids:
                    errs.append(f"{t['id']}: waits for unknown task {w}")
        owns = [(l["id"], p) for l in st["lanes"] for p in l.get("owns", [])]
        for i, (l1, p1) in enumerate(owns):
            for l2, p2 in owns[i + 1:]:
                if l1 != l2 and _nested(p1, p2):
                    errs.append(f"ownership overlap: {l1} owns {p1}, {l2} owns {p2}")
        for l in st["lanes"]:
            if not l.get("owns"):
                errs.append(f"lane {l['id']} owns no paths")
            if not any(s.get("lane") == l["id"] for s in st.get("sessions", [])):
                errs.append(f"lane {l['id']} has no session")
        graph = {t["id"]: t.get("waits", []) for t in st["tasks"]}
        done, stack = set(), set()

        def visit(n):
            if n in stack:
                errs.append(f"dependency cycle through {n}")
                return
            if n in done:
                return
            stack.add(n)
            for m in graph.get(n, []):
                visit(m)
            stack.discard(n)
            done.add(n)
        for n in graph:
            visit(n)
        for s in st.get("sessions", []):
            if s.get("state") not in SESSION_STATES:
                errs.append(f"session {s['name']}: bad state {s.get('state')}")
        if errs:
            print("INVALID:\n- " + "\n- ".join(sorted(set(errs))))
            sys.exit(1)
        print(f"valid: {len(st['tasks'])} tasks, {len(st['lanes'])} lanes, {len(st.get('sessions', []))} sessions")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", default=os.environ.get("BOARD_DOCS"), help="project docs folder holding state.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create state.json and register the project")
    p.add_argument("--id", required=True); p.add_argument("--name", required=True); p.add_argument("--code")
    p.add_argument("--phase"); p.add_argument("--target")
    p.add_argument("--gates", help="semicolon-separated list of steps only the user opens")
    p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_init)

    p = sub.add_parser("lane", help="add or update a lane")
    p.add_argument("id"); p.add_argument("--label"); p.add_argument("--owns", help="comma list of paths")
    p.set_defaults(f=cmd_lane)

    p = sub.add_parser("task-add", help="add a task (or --update one)")
    p.add_argument("id"); p.add_argument("--title"); p.add_argument("--lane"); p.add_argument("--waits")
    p.add_argument("--update", action="store_true"); p.add_argument("--by")
    p.add_argument("--optional", action="store_true", help="exists on the board but doesn't count toward progress or done")
    p.set_defaults(f=cmd_task_add)

    p = sub.add_parser("task", help="set a task's state, commit or progress note")
    p.add_argument("id"); p.add_argument("--state", choices=TASK_STATES); p.add_argument("--commit")
    p.add_argument("--note"); p.add_argument("--by"); p.add_argument("--force", action="store_true")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--optional", action="store_true", help="stop counting this task toward progress and done")
    g.add_argument("--required", action="store_true", help="count it again")
    p.set_defaults(f=cmd_task)

    p = sub.add_parser("qa", help="record a QA verdict on the submitted commit (pass marks done)")
    p.add_argument("id"); p.add_argument("--verdict", choices=["pass", "fail"], required=True)
    p.add_argument("--sha", required=True); p.add_argument("--issues", type=int, default=0)
    p.add_argument("--classes", help="FAIL: why, comma list of " + ",".join(FAIL_CLASSES))
    p.add_argument("--by"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_qa)

    p = sub.add_parser("session", help="add or update one session")
    p.add_argument("name"); p.add_argument("--role"); p.add_argument("--lane")
    p.add_argument("--state", choices=SESSION_STATES); p.add_argument("--doing"); p.add_argument("--note")
    p.add_argument("--commit"); p.add_argument("--msg")
    p.add_argument("--asked", action="store_true", help="orchestrator asked this session for a status line")
    p.add_argument("--no-seen", action="store_true", help="don't bump last-seen (use when marking another session)")
    p.set_defaults(f=cmd_session)

    p = sub.add_parser("sync", help="orchestrator: set several sessions at once, name=state[:doing]")
    p.add_argument("pairs", nargs="+"); p.add_argument("--by"); p.set_defaults(f=cmd_sync)

    p = sub.add_parser("ask", help="add an item waiting on you; prints its id")
    p.add_argument("id", nargs="?", help="omit to auto-number (D1, G1, S1 ...)")
    p.add_argument("--kind", choices=["decision", "gate", "stuck"], default="decision")
    p.add_argument("--question", required=True); p.add_argument("--options", help="a | b | c")
    p.add_argument("--recommend"); p.add_argument("--why"); p.add_argument("--blocks")
    p.add_argument("--session", help="for stuck items: the session (prevents duplicate pings)")
    p.add_argument("--by"); p.set_defaults(f=cmd_ask)

    p = sub.add_parser("answer", help="close a waiting item with the user's answer or what happened")
    p.add_argument("id"); p.add_argument("--answer", required=True); p.add_argument("--by")
    p.add_argument("--from-app", action="store_true", help="answer given in the Conductor app"); p.set_defaults(f=cmd_answer)

    p = sub.add_parser("ack", help="orchestrator: an app answer has been recorded and announced")
    p.add_argument("id"); p.add_argument("--by"); p.set_defaults(f=cmd_ack)

    p = sub.add_parser("wait-answer", help="orchestrator, in the background: block until the user answers in the app, then print it")
    p.set_defaults(f=cmd_wait_answer)
    p = sub.add_parser("note", help="add an event line"); p.add_argument("text"); p.add_argument("--by"); p.set_defaults(f=cmd_note)
    p = sub.add_parser("heartbeat", help="orchestrator heartbeat"); p.add_argument("--by"); p.add_argument("--phase"); p.set_defaults(f=cmd_heartbeat)
    p = sub.add_parser("summary", help="one-screen summary for the orchestrator and after compaction"); p.set_defaults(f=cmd_summary)
    p = sub.add_parser("watchdog", help="ping the user if the orchestrator heartbeat is stale (for launchd/cron)")
    p.add_argument("--max-min", type=int, default=45); p.add_argument("--repeat-min", type=int, default=120); p.set_defaults(f=cmd_watchdog)
    p = sub.add_parser("run", help="run a command in one of N shared slots: run [--pool browser] --slots 2 -- <cmd>")
    p.add_argument("--slots", type=int, default=2); p.add_argument("--pool", help="slot pool name (default tests)")
    p.add_argument("--cwd", help="run the command in this folder (QA: its own copy, never the shared tree)")
    p.add_argument("cmd", nargs=argparse.REMAINDER); p.set_defaults(f=cmd_run)
    p = sub.add_parser("stats", help="measured outcomes: first-pass QA yield, fails, waiting items; --all for every registered build")
    p.add_argument("--all", action="store_true"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_stats)
    p = sub.add_parser("render", help="re-render STATUS.md"); p.set_defaults(f=cmd_render)
    p = sub.add_parser("validate", help="check lanes, ownership overlap, dependencies"); p.set_defaults(f=cmd_validate)

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    a = ap.parse_args()
    if not a.docs and not getattr(a, "all", False):
        die("pass --docs <absolute docs folder> (or set BOARD_DOCS)")
    check_args(a)
    a.f(a)


if __name__ == "__main__":
    main()
