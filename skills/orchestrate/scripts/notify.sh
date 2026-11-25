#!/bin/sh
# Ping the user: Telegram message + a desktop notification (macOS, Windows via Git Bash, or Linux).
# Usage: notify.sh "<project> · <kind>" "<message>"
#   kind is one of: decision needed, go needed, session stuck, paused, finished (anything else works too)
#   In the message, put the ask first; an optional last sentence starting "Answer in" or "Check"
#   becomes the action line.
# Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from ~/.conductor/telegram.env. Never prints the token.
# Exit 0: Telegram sent (seen anywhere).
# Exit 3: only the desktop notification showed (seen only at this computer) - say so in your terminal.
# Exit 1: nothing reached the user.

title="${1:-Conductor}"
body="${2:-}"
env_file="$HOME/.conductor/telegram.env"
tg=0
mac=0

val() { sed -n "s/^\(export \)\{0,1\}$1=//p" "$env_file" | tail -n 1 | tr -d "\"'[:space:]"; }
html() { printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g'; }

project=$(printf '%s' "$title" | sed 's/ · .*//')
kind=$(printf '%s' "$title" | sed -n 's/^[^·]* · //p')
case "$kind" in
  *decision*) icon="❓" ;;
  *go*)       icon="🟠" ;;
  *stuck*|*silent*) icon="⚠️" ;;
  *paus*)     icon="⏸" ;;
  *finish*|*done*) icon="✅" ;;
  *)          icon="🔔" ;;
esac
# Split off a trailing "Answer in …" / "Check …" sentence as the action line.
action=$(printf '%s' "$body" | sed -n 's/.*\(\(Answer in\|Check\|Type go\) [^.]*\.\{0,1\}\)$/\1/p')
main="$body"
[ -n "$action" ] && main=$(printf '%s' "$body" | sed "s/[[:space:]]*$(printf '%s' "$action" | sed 's/[][\/.*^$]/\\&/g')\$//")

text="$icon <b>$(html "$project")</b>"
[ -n "$kind" ] && text="$text · $(html "$kind")"
text="$text

$(html "$main")"
[ -n "$action" ] && text="$text

<i>$(html "$action")</i>"

if [ -r "$env_file" ]; then
  token=$(val TELEGRAM_BOT_TOKEN)
  chat=$(val TELEGRAM_CHAT_ID)
  if [ -n "$token" ] && [ -n "$chat" ]; then
    resp=$(curl -s -m 20 "https://api.telegram.org/bot${token}/sendMessage" \
      --data-urlencode "chat_id=${chat}" \
      --data-urlencode "parse_mode=HTML" \
      --data-urlencode "disable_web_page_preview=true" \
      --data-urlencode "text=${text}" 2>/dev/null)
    case "$resp" in
      *'"ok":true'*) echo "telegram: sent"; tg=1 ;;
      *) echo "telegram: failed ($(printf '%s' "$resp" | sed -n 's/.*"description":"\([^"]*\)".*/\1/p'))" ;;
    esac
  else
    echo "telegram: not configured (token or chat id missing in $env_file)"
  fi
else
  echo "telegram: not configured ($env_file missing)"
fi

if command -v osascript >/dev/null 2>&1; then
  esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
  if osascript -e "display notification \"$(esc "$body")\" with title \"$(esc "$title")\" sound name \"Glass\"" >/dev/null 2>&1; then
    echo "mac: shown"; mac=1
  fi
fi

# Windows (Git Bash): a tray balloon via PowerShell. Title and body go in through the environment,
# never into the script text, so no quote in a message can break out of it.
if [ "$mac" -eq 0 ] && command -v powershell.exe >/dev/null 2>&1; then
  if NOTIFY_TITLE="$title" NOTIFY_BODY="$body" powershell.exe -NoProfile -NonInteractive -Command '
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Information
    $n.Visible = $true
    $n.ShowBalloonTip(10000, $env:NOTIFY_TITLE, $env:NOTIFY_BODY, "Info")
    Start-Sleep -Seconds 5
    $n.Dispose()' >/dev/null 2>&1; then
    echo "windows: shown"; mac=1
  fi
fi

# Linux desktop
if [ "$mac" -eq 0 ] && command -v notify-send >/dev/null 2>&1; then
  if notify-send "$title" "$body" >/dev/null 2>&1; then
    echo "desktop: shown"; mac=1
  fi
fi

[ "$tg" -eq 1 ] && exit 0
[ "$mac" -eq 1 ] && exit 3
exit 1
