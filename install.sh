#!/bin/sh
# Installs the orchestrate skill and its two helper agents into ~/.claude.
# Never deletes anything: an existing copy is moved aside to <name>.bak-<timestamp>.
# Usage: ./install.sh            install (refuses if a copy is already there)
#        ./install.sh --replace  move the old copy aside, then install
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE="${CLAUDE_HOME:-$HOME/.claude}"
STAMP="$(date +%Y%m%d-%H%M%S)"
replace=0
[ "${1:-}" = "--replace" ] && replace=1

# Python 3: python3 on macOS/Linux; on Windows usually the py launcher (python3 can be a Store stub).
PY=""
for c in "python3" "py -3" "python"; do
  if $c -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Python 3 is required (board.py and Conductor use it). Install it from python.org."; exit 1; }

place() { # place <src> <dest>
  if [ -e "$2" ]; then
    if [ "$replace" -eq 0 ]; then
      echo "already installed: $2"
      echo "run ./install.sh --replace to move it aside to $2.bak-$STAMP and install this version"
      exit 1
    fi
    mv "$2" "$2.bak-$STAMP"
    echo "moved old copy to $2.bak-$STAMP"
  fi
  cp -R "$1" "$2"
}

mkdir -p "$CLAUDE/skills" "$CLAUDE/agents"
place "$HERE/skills/orchestrate" "$CLAUDE/skills/orchestrate"
place "$HERE/agents/orchestrate-builder.md" "$CLAUDE/agents/orchestrate-builder.md"
place "$HERE/agents/orchestrate-qa.md" "$CLAUDE/agents/orchestrate-qa.md"
chmod +x "$CLAUDE/skills/orchestrate/scripts/notify.sh" "$HERE/conductor/Conductor.command" 2>/dev/null || true
mkdir -p "$HOME/.conductor"

echo "installed orchestrate $(cat "$HERE/skills/orchestrate/VERSION"): $CLAUDE/skills/orchestrate, orchestrate-builder and orchestrate-qa agents"
echo "python: $PY  (the skill uses this command for board.py)"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) echo "dashboard: double-click conductor\\Conductor.cmd, or run: $PY \"$HERE/conductor/start.py\"" ;;
  *) echo "dashboard: $PY \"$HERE/conductor/start.py\"" ;;
esac
