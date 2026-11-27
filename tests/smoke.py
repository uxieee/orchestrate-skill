#!/usr/bin/env python3
"""End-to-end smoke test on the real OS (Windows, macOS, Linux). Stdlib only.

Installs into a throwaway home folder, drives board.py through a small build (including the safety
refusals, concurrent writers and the shared test slots), runs notify.sh and the watchdog, starts
Conductor with start.py and talks to its API. On Windows it also schedules the watchdog with Task
Scheduler. Everything it creates lives in one temp folder that it removes at the end.

    python tests/smoke.py
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = os.name == "nt"
PY = sys.executable
FAILS = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        FAILS.append(what)


def git_bash():
    if not WINDOWS:
        return shutil.which("bash") or "/bin/sh"
    for b in (os.path.expandvars(r"%ProgramFiles%\Git\bin\bash.exe"), shutil.which("bash")):
        if b and os.path.isfile(b) and "system32" not in b.lower():
            return b
    raise SystemExit("Git Bash not found")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    tmp = tempfile.mkdtemp(prefix="orchestrate-smoke-")
    server_pid = None
    task_name = None
    try:
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        env = dict(os.environ, HOME=home, USERPROFILE=home, PYTHONUTF8="0")
        for k in list(env):
            if k.startswith("CONDUCTOR_") or k.startswith("CLAUDE"):
                env.pop(k)
        port = free_port()
        env["CONDUCTOR_PORT"] = str(port)
        bash = git_bash()

        def sh(args, **kw):
            return subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)

        # ---- install
        r = sh([bash, os.path.join(ROOT, "install.sh")])
        print(r.stdout.strip())
        check(r.returncode == 0, f"install.sh exits 0 ({r.stderr.strip()[-200:]})")
        board = os.path.join(home, ".claude", "skills", "orchestrate", "scripts", "board.py")
        check(os.path.isfile(board), "board.py installed under the home folder")
        with open(os.path.join(ROOT, "skills", "orchestrate", "VERSION"), encoding="utf-8") as f:
            version = f.read().strip()
        check(re.fullmatch(r"\d+\.\d+\.\d+", version) is not None, f"VERSION is x.y.z ({version})")
        check(f"installed orchestrate {version}:" in r.stdout, "install.sh reports the version")
        tag = os.environ.get("GITHUB_REF_NAME", "") if os.environ.get("GITHUB_REF_TYPE") == "tag" else ""
        check(not tag or tag == "v" + version, f"release tag matches VERSION ({tag or 'not a tag'})")
        r = sh([bash, os.path.join(ROOT, "install.sh")])
        check(r.returncode == 1 and "already installed" in r.stdout, "second install refuses")

        docs = os.path.join(tmp, "build", "docs")
        code = os.path.join(tmp, "build", "code")
        os.makedirs(code)

        def B(*args):
            return sh([PY, board, "--docs", docs, *args])

        def ok(*args):
            r = B(*args)
            check(r.returncode == 0, "board " + " ".join(args[:3]) + (f" -> {r.stderr.strip()}" if r.returncode else ""))
            return r

        # ---- a small build
        ok("init", "--id", "sm", "--name", "Smoke · Build", "--code", code, "--gates", "deploy to live")
        ok("lane", "api", "--label", "API", "--owns", "src/api")
        ok("lane", "web", "--label", "Web", "--owns", "src/web")
        ok("session", "sm-api", "--role", "implementer", "--lane", "api", "--no-seen")
        ok("session", "sm-web", "--role", "implementer", "--lane", "web", "--no-seen")
        ok("session", "sm-qa", "--role", "qa", "--no-seen")
        ok("session", "sm-orchestrator", "--role", "orchestrator", "--no-seen")
        ok("task-add", "T1", "--title", "API route", "--lane", "api")
        ok("task-add", "T2", "--title", "Web page", "--lane", "web", "--waits", "T1")
        ok("task-add", "T3", "--title", "Nice extra", "--lane", "web", "--optional")
        ok("task-add", "T4", "--title", "Deploy", "--lane", "orchestrator", "--waits", "T1,T2")
        r = ok("validate")
        check("valid" in r.stdout, "validate passes")
        for st in ("assigned", "progress"):
            ok("task", "T1", "--state", st)
        ok("task", "T1", "--state", "qa", "--commit", "abc1234")
        r = B("qa", "T1", "--verdict", "pass", "--sha", "fff0000")
        check(r.returncode == 2, "QA pass on the wrong commit is refused")
        r = B("task", "T2", "--state", "done")
        check(r.returncode == 2, "done without QA is refused")
        r = B("task-add", "<img src=x>", "--title", "x", "--lane", "api")
        check(r.returncode == 2, "html in a task id is refused")
        ok("qa", "T1", "--verdict", "pass", "--sha", "abc1234")
        r = ok("summary")
        check("33% (1/3)" in r.stdout and "+1 optional" in r.stdout, f"summary counts required tasks only ({r.stdout.splitlines()[0]})")
        with open(os.path.join(docs, "STATUS.md"), encoding="utf-8") as f:
            check("Smoke · Build" in f.read(), "STATUS.md written as UTF-8")

        # ---- ownership overlap is caught on every OS (Windows paths use backslashes)
        ok("lane", "core", "--label", "Core", "--owns", "src")
        r = B("validate")
        check(r.returncode != 0 and "ownership overlap" in (r.stdout + r.stderr), "validate catches nested ownership (src vs src/api)")
        ok("lane", "core", "--label", "Core", "--owns", "lib")

        # ---- concurrent writers: the lock must keep every write
        procs = [subprocess.Popen([PY, board, "--docs", docs, "note", f"parallel-{i}", "--by", "sm-api"], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for i in range(8)]
        codes = [p.wait(60) for p in procs]
        with open(os.path.join(docs, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        texts = " ".join(e["text"] for e in st["events"])
        check(all(c == 0 for c in codes) and all(f"parallel-{i}" in texts for i in range(8)),
              f"8 parallel writers all land (exit codes {codes})")

        # ---- shared test slots serialize
        t0 = time.time()
        sleeper = [PY, "-c", "import time; time.sleep(1.5)"]
        procs = [subprocess.Popen([PY, board, "--docs", docs, "run", "--slots", "1", "--", *sleeper], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
        codes = [p.wait(60) for p in procs]
        took = time.time() - t0
        check(all(c == 0 for c in codes) and took >= 3.0, f"run --slots 1 makes two runs take turns ({took:.1f}s)")
        r = B("run", "--", PY, "-c", "import sys; sys.exit(7)")
        check(r.returncode == 7, "run passes the command's exit code through")

        # ---- notify.sh without Telegram: desktop only (3) or nothing (1), never a crash
        notify = os.path.join(home, ".claude", "skills", "orchestrate", "scripts", "notify.sh")
        r = sh([bash, notify, "Smoke · finished", "Pings work. Check the tab."], timeout=60)
        print("   notify:", r.stdout.strip().replace("\n", " | "))
        check(r.returncode in (1, 3) and "not configured" in r.stdout, f"notify.sh without Telegram exits 1 or 3 (got {r.returncode})")

        # ---- watchdog: no heartbeat -> pings once, leaves a flag
        r = B("watchdog")
        check(r.returncode == 0 and os.path.exists(os.path.join(docs, ".watchdog-pinged")), f"watchdog pings ({r.stderr.strip()[-160:]})")
        r = B("watchdog")
        check("already pinged" in r.stdout, "watchdog doesn't ping twice")

        # ---- Windows: schedule the watchdog with Task Scheduler, run it, remove it
        if WINDOWS:
            os.remove(os.path.join(docs, ".watchdog-pinged"))
            cmd_file = os.path.join(docs, "watchdog.cmd")
            with open(cmd_file, "w", encoding="utf-8") as f:
                f.write(f'@set "USERPROFILE={home}"\r\n@set "HOME={home}"\r\n@"{PY}" "{board}" --docs "{docs}" watchdog\r\n')
            task_name = f"conductor-smoke-{port}"
            r = sh(["schtasks", "/Create", "/SC", "MINUTE", "/MO", "15", "/TN", task_name, "/TR", f'"{cmd_file}"', "/F"])
            check(r.returncode == 0, f"schtasks /Create ({(r.stdout + r.stderr).strip()[-160:]})")
            sh(["schtasks", "/Run", "/TN", task_name])
            flag = os.path.join(docs, ".watchdog-pinged")
            for _ in range(60):
                if os.path.exists(flag):
                    break
                time.sleep(1)
            check(os.path.exists(flag), "the scheduled watchdog ran and pinged")
            r = sh(["schtasks", "/Delete", "/TN", task_name, "/F"])
            check(r.returncode == 0, "schtasks /Delete")
            task_name = None

        # ---- Conductor: live sessions without signalling anyone
        sess = os.path.join(home, ".claude", "sessions")
        os.makedirs(sess)
        dead = subprocess.Popen([PY, "-c", "pass"])
        dead.wait()
        with open(os.path.join(sess, f"{os.getpid()}.json"), "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "name": "sm-api", "status": "busy", "startedAt": 2}, f)
        with open(os.path.join(sess, f"{dead.pid}.json"), "w", encoding="utf-8") as f:
            json.dump({"pid": dead.pid, "name": "sm-web", "status": "idle", "startedAt": 1}, f)

        r = sh([PY, os.path.join(ROOT, "conductor", "start.py"), "--no-open"], timeout=60)
        check(r.returncode == 0 and f":{port}/" in r.stdout, f"start.py starts Conductor ({r.stdout.strip()[-160:]})")
        pidf = os.path.join(home, ".conductor", "server.pid")
        if os.path.exists(pidf):
            server_pid = int(open(pidf, encoding="utf-8").read().strip())
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(base + "/api/state", timeout=10) as resp:
            state = json.load(resp)
        p = next((x for x in state["projects"] if x["id"] == "sm"), None)
        check(p is not None, "Conductor lists the build")
        live = {s["name"]: s.get("live", {}).get("alive") for s in (p or {}).get("sessions", [])}
        check(live.get("sm-api") is True and live.get("sm-web") is False, f"session liveness read without signals ({live})")
        r = sh([PY, os.path.join(ROOT, "conductor", "start.py"), "--no-open"], timeout=30)
        check(r.returncode == 0, "start.py again reuses the running server")

        # ---- answering from the app wakes wait-answer
        D = B("ask", "--kind", "decision", "--question", "Blue or green?", "--options", "blue | green", "--by", "sm-orchestrator").stdout.strip()
        G = B("ask", "--kind", "gate", "--question", "Ready for deploy", "--by", "sm-orchestrator").stdout.strip()
        waiter = subprocess.Popen([PY, board, "--docs", docs, "wait-answer"], env=env, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        time.sleep(2)

        def post(body, origin=base):
            req = urllib.request.Request(base + "/api/answer", data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Origin": origin})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status
            except urllib.error.HTTPError as e:
                return e.code

        check(post({"project": "sm", "id": D, "answer": "blue"}) == 200, "answer a decision from the app")
        check(post({"project": "sm", "id": G, "answer": "go"}) == 403, "a gate can't be opened from the app")
        check(post({"project": "sm", "id": D, "answer": "x"}, origin="https://evil.example") == 403, "other websites are refused")
        try:
            out, _ = waiter.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            waiter.kill()
            out = ""
        check("ANSWERED IN APP" in out and "blue" in out, "wait-answer wakes on the app answer")
    finally:
        if task_name:
            subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)
        if server_pid:
            try:
                if WINDOWS:
                    subprocess.run(["taskkill", "/PID", str(server_pid), "/F"], capture_output=True)
                else:
                    os.kill(server_pid, 15)
            except OSError:
                pass
            time.sleep(1)
        shutil.rmtree(tmp, ignore_errors=True)
        check(not os.path.exists(tmp), "temp folder removed")
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
