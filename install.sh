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

command -v python3 >/dev/null 2>&1 || { echo "python3 is required (board.py and Conductor use it)."; exit 1; }

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

echo "installed: $CLAUDE/skills/orchestrate, orchestrate-builder and orchestrate-qa agents"
echo "dashboard: python3 \"$HERE/conductor/server.py\"  then open http://127.0.0.1:4747/"
