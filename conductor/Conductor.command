#!/bin/bash
# Starts the Conductor server (if it isn't running) and opens the board in your browser.
# Run by Conductor.app through Terminal, which already has access to this drive. The server runs
# detached in the background (log: ~/.conductor/server.log), so this Terminal window closes itself.
# The server keeps running until the Mac restarts; opening the app again reuses it.
cd "$(dirname "$0")" || exit 1
# If a Claude Code session launched this, drop its session markers so nothing started from here
# is mistaken for that session's child.
for v in $(env | grep -o '^CLAUDE[A-Z_]*'); do unset "$v"; done
PORT=4747
URL="http://127.0.0.1:$PORT/"

# Opens in your default browser. For a tab-less app window instead, set CONDUCTOR_APP_WINDOW=1.
open_window() {
  if [ -n "$CONDUCTOR_APP_WINDOW" ] && [ -d "/Applications/Google Chrome.app" ]; then
    open -na "Google Chrome" --args --app="$URL" --window-size=1440,900
  else
    open "$URL"
  fi
}

# Close the launcher windows a moment after this script exits (safe: the server is not in one).
close_me() {
  ( sleep 1; osascript -e 'tell application "Terminal" to close (every window whose name contains "Conductor.command")' ) >/dev/null 2>&1 &
  disown
}

if ! curl -s -o /dev/null -m 2 "${URL}api/state"; then
  mkdir -p "$HOME/.conductor"
  nohup python3 server.py >>"$HOME/.conductor/server.log" 2>&1 &
  disown
  for _ in $(seq 1 50); do
    curl -s -o /dev/null -m 1 "${URL}api/state" && break
    sleep 0.2
  done
  if ! curl -s -o /dev/null -m 1 "${URL}api/state"; then
    echo "Conductor's server didn't start. Last lines of ~/.conductor/server.log:"
    tail -n 20 "$HOME/.conductor/server.log"
    exit 1
  fi
fi
open_window
close_me
exit 0
