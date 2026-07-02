#!/bin/bash
# Run the invisible agent Chrome instance.
#
# --no-startup-window: the process starts with zero windows, so launch never
# activates the app. The sentinel then keeps every window permanently
# minimized, enforced event-driven over CDP the moment a target appears, so
# agent-opened tabs never paint on screen. `show`/`hide` give the operator
# deliberate access for logins/2FA.
set -euo pipefail

CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# launchd's PATH does not include homebrew; resolve node explicitly.
NODE_BIN="${AGENT_BROWSER_NODE:-/opt/homebrew/bin/node}"
DATA_DIR="${AGENT_BROWSER_DATA_DIR:-$HOME/.agent-chrome}"
PROFILE="${AGENT_BROWSER_PROFILE:-Profile 2}"
PORT="${AGENT_BROWSER_CDP_PORT:-9222}"
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

"$CHROME_BIN" \
  --user-data-dir="$DATA_DIR" \
  --profile-directory="$PROFILE" \
  --remote-debugging-port="$PORT" \
  --no-startup-window \
  --no-first-run \
  --no-default-browser-check \
  --hide-crash-restore-bubble \
  --disable-session-crashed-bubble \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding &
CHROME_PID=$!

for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done

# Restart the sentinel if it ever dies while Chrome is alive.
while kill -0 "$CHROME_PID" 2>/dev/null; do
  "$NODE_BIN" "$BASE_DIR/scripts/sentinel.mjs" || true
  sleep 1
done
