#!/usr/bin/env python3
"""Start Conductor (if it isn't running) and open it in the browser. Works on Windows, macOS, Linux.

The server runs detached in the background (log: ~/.conductor/server.log) and keeps running until
you log out or restart; running this again reuses it.
  python3 start.py            start + open the browser
  python3 start.py --no-open  start only (prints the URL)
"""
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("CONDUCTOR_PORT", "4747"))
URL = f"http://127.0.0.1:{PORT}/"
LOG_DIR = os.path.expanduser("~/.conductor")


def up():
    try:
        with urllib.request.urlopen(URL + "api/state", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start():
    os.makedirs(LOG_DIR, exist_ok=True)
    # Started from a Claude Code session? Drop its markers so the server isn't taken for its child.
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    log = open(os.path.join(LOG_DIR, "server.log"), "ab")
    kw = {"cwd": HERE, "env": env, "stdin": subprocess.DEVNULL, "stdout": log, "stderr": log}
    if os.name == "nt":
        # 0x8 DETACHED_PROCESS | 0x200 CREATE_NEW_PROCESS_GROUP | 0x08000000 CREATE_NO_WINDOW
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
    else:
        kw["start_new_session"] = True
    subprocess.Popen([sys.executable, os.path.join(HERE, "server.py")], **kw)
    for _ in range(50):
        if up():
            return True
        time.sleep(0.2)
    return False


def main():
    if not up() and not start():
        print("Conductor's server didn't start. Last lines of ~/.conductor/server.log:")
        try:
            with open(os.path.join(LOG_DIR, "server.log"), encoding="utf-8", errors="replace") as f:
                print("".join(f.readlines()[-20:]))
        except OSError:
            pass
        sys.exit(1)
    print(f"Conductor is running: {URL}")
    if "--no-open" not in sys.argv:
        webbrowser.open(URL)


if __name__ == "__main__":
    main()
