#!/bin/bash
# Windows only, run in Git Bash: drives the skill exactly the way Claude Code on Windows does,
# with "$HOME/..." paths and POSIX-style folders (/c/Users/...), the Python command install.sh
# picks, notify.sh called directly, the watchdog scheduled with the exact schtasks line SKILL.md
# gives, and Conductor started by Conductor.cmd. Removes everything it creates.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
check() { if [ "$1" = 0 ]; then echo "ok   $2"; else echo "FAIL $2"; fails=$((fails + 1)); fi; }

T="$(mktemp -d)"
export HOME="$T/home"; mkdir -p "$HOME"
export USERPROFILE="$(cygpath -w "$HOME")"        # what Python's expanduser reads on Windows
export CONDUCTOR_PORT=4791
unset CONDUCTOR_REGISTRY
TASK="conductor-gitbash-smoke-$$"
cleanup() {
  MSYS_NO_PATHCONV=1 schtasks /Delete /TN "$TASK" /F >/dev/null 2>&1
  [ -f "$HOME/.conductor/server.pid" ] && MSYS_NO_PATHCONV=1 taskkill /PID "$(cat "$HOME/.conductor/server.pid")" /F >/dev/null 2>&1
  sleep 1; rm -rf "$T"; [ ! -e "$T" ]; check $? "temp folder removed"
  echo; [ "$fails" = 0 ] && echo "all passed" || echo "$fails failed"
}
trap 'cleanup; exit $([ "$fails" = 0 ] && echo 0 || echo 1)' EXIT

out="$("$ROOT/install.sh")"; check $? "install.sh in Git Bash"
echo "$out"
PY="$(printf '%s\n' "$out" | sed -n 's/^python: \(.*\)  (the skill.*/\1/p')"
[ -n "$PY" ]; check $? "installer picked a Python command ($PY)"

# The skill's own command shape: <python> "$HOME/.claude/skills/orchestrate/scripts/board.py" --docs "<abs docs>"
DOCS="$HOME/work/projects/demo/docs"
B() { $PY "$HOME/.claude/skills/orchestrate/scripts/board.py" --docs "$DOCS" "$@"; }
mkdir -p "$HOME/work/projects/demo/code"
B init --id demo --name "Demo · Build" --code "$HOME/work/projects/demo/code" --gates "deploy to live" >/dev/null; check $? "board init with a POSIX docs path"
[ -f "$DOCS/state.json" ] && [ -f "$DOCS/STATUS.md" ]; check $? "state.json and STATUS.md landed where Git Bash expects them"
B lane api --label "API" --owns "src/api" >/dev/null; check $? "lane"
B session demo-api --role implementer --lane api --no-seen >/dev/null; check $? "session"
B session demo-orchestrator --role orchestrator --no-seen >/dev/null; check $? "session (orchestrator)"
B task-add T1 --title "API route" --lane api >/dev/null; check $? "task-add"
B task-add T2 --title "Extra" --lane api --optional >/dev/null; check $? "task-add --optional"
B task T1 --state assigned >/dev/null && B task T1 --state progress >/dev/null && B task T1 --state qa --commit "p:01d784ae,k:f405359a" >/dev/null
check $? "task moves, multi-repo commit ref"
B qa T1 --verdict pass --sha "p:01d784ae,k:f405359a" >/dev/null; check $? "qa pass on that ref"
s="$(B summary)"; echo "$s" | head -1
echo "$s" | grep -q "ALL TASKS DONE"; check $? "summary: required done, optional ignored"
grep -q "Demo · Build" "$DOCS/STATUS.md"; check $? "STATUS.md is UTF-8"
B run --cwd "$HOME/work/projects/demo/code" --slots 1 -- $PY -c "print('slot-ok')" | grep -q slot-ok; check $? "board run in a slot"
reg="$(cat "$HOME/.conductor/projects.json")"
echo "$reg" | grep -q 'demo'; check $? "registered in ~/.conductor/projects.json"

# notify.sh called directly, as the templates do
"$HOME/.claude/skills/orchestrate/scripts/notify.sh" "Demo · finished" "Pings work. Check the tab."; rc=$?
[ "$rc" = 3 ] || [ "$rc" = 1 ]; check $? "notify.sh runs directly in Git Bash (exit $rc)"

# Watchdog with the exact schtasks line from SKILL.md step 4
WDOCS="$(cygpath -w "$DOCS")"
printf '@%s "%s" --docs "%s" watchdog\r\n' "$PY" "$(cygpath -w "$HOME/.claude/skills/orchestrate/scripts/board.py")" "$WDOCS" > "$DOCS/watchdog.cmd"
MSYS_NO_PATHCONV=1 schtasks /Create /SC MINUTE /MO 15 /TN "$TASK" /TR "\"$WDOCS\\watchdog.cmd\"" /F >/dev/null; check $? "schtasks /Create as SKILL.md writes it"
MSYS_NO_PATHCONV=1 schtasks /Query /TN "$TASK" >/dev/null; check $? "schtasks /Query"
MSYS_NO_PATHCONV=1 schtasks /Run /TN "$TASK" >/dev/null
for i in $(seq 1 60); do [ -f "$DOCS/.watchdog-pinged" ] && break; sleep 1; done
[ -f "$DOCS/.watchdog-pinged" ]; check $? "scheduled watchdog ran and pinged"
MSYS_NO_PATHCONV=1 schtasks /Delete /TN "$TASK" /F >/dev/null; check $? "schtasks /Delete"

# Conductor.cmd, the Windows double-click launcher
cmd //c "$(cygpath -w "$ROOT/conductor/Conductor.cmd")" --no-open; check $? "Conductor.cmd starts Conductor"
curl -s -m 5 "http://127.0.0.1:$CONDUCTOR_PORT/api/state" | grep -q '"id": "demo"'; check $? "Conductor serves the build"
D="$(B ask --kind decision --question "Blue or green?" --options "blue | green" --by demo-orchestrator)"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$CONDUCTOR_PORT/api/answer" \
  -H "Origin: http://127.0.0.1:$CONDUCTOR_PORT" -H 'Content-Type: application/json' \
  -d "{\"project\":\"demo\",\"id\":\"$D\",\"answer\":\"blue\"}")"
[ "$code" = 200 ]; check $? "answer from the app ($code)"
B summary | grep -q "ANSWERED IN APP.*blue"; check $? "board sees the app answer"
