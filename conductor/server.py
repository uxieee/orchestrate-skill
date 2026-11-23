#!/usr/bin/env python3
"""Conductor local server.

Serves the board UI from ./ui and these endpoints:
  GET  /api/state    every registered project's board (from ~/.conductor/projects.json), each
                     session enriched with `live` from Claude Code's own session files
  POST /api/answer   {project, id, answer} -> board.py answer --from-app (decisions only, never gates)
  POST /api/project  {project, action: archive | unarchive | remove} -> edits the registry only;
                     never touches a project's files

Binds to 127.0.0.1 only. POSTs must come from this page's own origin, so no other website can
answer for you. Runs until the Mac restarts. It must not stop itself when no page is polling:
browsers pause or freeze background tabs, so silence doesn't mean the window was closed.
"""
import fcntl
import json
import os
import subprocess
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CONDUCTOR_PORT", "4747"))
HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
REGISTRY = os.path.expanduser("~/.conductor/projects.json")
BOARD = os.path.expanduser("~/.claude/skills/orchestrate/scripts/board.py")
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}  # anything else is a website using DNS rebinding
EVENTS_SENT = 60
SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")


def live_sessions():
    """name -> {alive, status, since}. Reads only the plain <pid>.json status files Claude Code
    writes for each running session (never the .key files), and checks the process is alive."""
    out = {}
    try:
        names = os.listdir(SESSIONS_DIR)
    except OSError:
        return out
    for fn in names:
        if not (fn.endswith(".json") and fn[:-5].isdigit()):
            continue
        try:
            with open(os.path.join(SESSIONS_DIR, fn)) as f:
                d = json.load(f)
            pid, name = int(d.get("pid") or fn[:-5]), d.get("name")
            if not name:
                continue
            os.kill(pid, 0)  # raises if the process is gone
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        prev = out.get(name)
        cur = {"alive": True, "status": d.get("status") or "unknown",
               "since": d.get("statusUpdatedAt") or d.get("updatedAt"), "startedAt": d.get("startedAt")}
        if not prev or (cur["startedAt"] or 0) > (prev["startedAt"] or 0):
            out[name] = cur
    return out


def edit_registry(fn):
    with open(REGISTRY + ".lock", "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        with open(REGISTRY) as f:
            reg = json.load(f)
        result = fn(reg)
        tmp = REGISTRY + ".tmp"
        with open(tmp, "w") as f:
            json.dump(reg, f, indent=2)
            f.write("\n")
        os.replace(tmp, REGISTRY)
        return result


def load_projects():
    projects, errors = [], []
    try:
        with open(REGISTRY) as f:
            reg = json.load(f)
    except FileNotFoundError:
        return projects, errors
    except Exception as e:  # unreadable registry
        return projects, [{"state": REGISTRY, "error": f"registry unreadable: {type(e).__name__}"}]
    live = live_sessions()
    for entry in reg.get("projects", []):
        path = entry.get("state")
        try:
            with open(path) as f:
                st = json.load(f)
            st["events"] = st.get("events", [])[-EVENTS_SENT:]
            st["statePath"] = path
            st["archived"] = bool(entry.get("archived"))
            st["archivedAt"] = entry.get("archivedAt")
            for s in st.get("sessions", []):
                s["live"] = live.get(s.get("name"), {"alive": False})
            projects.append(st)
        except FileNotFoundError:
            errors.append({"id": entry.get("id"), "name": entry.get("name"), "state": path, "error": "board file missing",
                           "archived": bool(entry.get("archived"))})
        except Exception as e:
            errors.append({"id": entry.get("id"), "name": entry.get("name"), "state": path, "error": type(e).__name__})
    return projects, errors


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=UI, **kw)

    def log_message(self, fmt, *args):  # keep the console quiet except for answers and errors
        pass

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def foreign_host(self):
        if (self.headers.get("Host") or "").lower() in HOSTS:
            return False
        self.send_json(403, {"error": "wrong host"})
        return True

    def do_GET(self):
        if self.foreign_host():
            return
        if self.path.split("?")[0] == "/api/state":
            projects, errors = load_projects()
            return self.send_json(200, {"now": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "projects": projects, "errors": errors})
        return super().do_GET()

    def do_POST(self):
        if self.foreign_host():
            return
        if self.path not in ("/api/answer", "/api/project"):
            return self.send_json(404, {"error": "not found"})
        if self.headers.get("Origin") not in ORIGINS or "application/json" not in (self.headers.get("Content-Type") or ""):
            return self.send_json(403, {"error": "changes are only accepted from the Conductor window"})
        if self.path == "/api/project":
            return self.project_action()
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
            pid, wid, answer = req["project"], req["id"], str(req["answer"]).strip()
        except Exception:
            return self.send_json(400, {"error": "bad request"})
        if not answer or len(answer) > 2000:
            return self.send_json(400, {"error": "answer is empty or too long"})
        projects, _ = load_projects()
        st = next((p for p in projects if p.get("id") == pid), None)
        if not st:
            return self.send_json(404, {"error": f"unknown project {pid}"})
        w = next((x for x in st.get("waiting", []) if x.get("id") == wid), None)
        if not w:
            return self.send_json(404, {"error": f"unknown item {wid}"})
        if w.get("kind") == "gate":
            return self.send_json(403, {"error": "gates open only when you type go in the orchestrator tab"})
        docs = os.path.dirname(st["statePath"])
        r = subprocess.run([sys.executable, BOARD, "--docs", docs, "answer", wid, "--answer", answer, "--from-app"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return self.send_json(409, {"error": (r.stderr or r.stdout).strip().replace("board: ", "")})
        print(f"answered {pid} {wid}: {answer}", flush=True)
        return self.send_json(200, {"ok": True, "id": wid})


    def project_action(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(min(n, 5000)) or b"{}")
            pid, action = req["project"], req["action"]
        except Exception:
            return self.send_json(400, {"error": "bad request"})
        if action not in ("archive", "unarchive", "remove"):
            return self.send_json(400, {"error": "unknown action"})

        def apply(reg):
            items = reg.get("projects", [])
            hit = [p for p in items if p.get("id") == pid]
            if not hit:
                return False
            if action == "remove":
                reg["projects"] = [p for p in items if p.get("id") != pid]
            for p in hit:
                if action == "archive":
                    p["archived"], p["archivedAt"] = True, time.strftime("%Y-%m-%dT%H:%M:%S%z")
                elif action == "unarchive":
                    p.pop("archived", None); p.pop("archivedAt", None)
            return True
        try:
            ok = edit_registry(apply)
        except Exception as e:
            return self.send_json(500, {"error": f"couldn't update the project list ({type(e).__name__})"})
        if not ok:
            return self.send_json(404, {"error": f"unknown project {pid}"})
        print(f"{action} {pid}", flush=True)
        return self.send_json(200, {"ok": True})


def main():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} is busy: Conductor is probably already running.", flush=True)
        sys.exit(3)
    print(f"Conductor on http://127.0.0.1:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
