#!/bin/bash
# Run the invisible agent Chrome instance.
#
# Default mode is --headless=new: the process never connects a window, so
# there is no Dock icon, no minimized-window tile, and nothing to steal
# focus — while CDP, the real profile, and screenshots all keep working.
# `show` flips a flag file and restarts this job headed for manual
# logins/2FA; `hide` flips it back to headless. The sentinel (window
# minimizer) is only needed in headed mode.
set -euo pipefail

CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# launchd's PATH does not include homebrew; resolve node explicitly.
NODE_BIN="${AGENT_BROWSER_NODE:-/opt/homebrew/bin/node}"
DATA_DIR="${AGENT_BROWSER_DATA_DIR:-$HOME/.agent-chrome}"
PROFILE="${AGENT_BROWSER_PROFILE:-Default}"
PORT="${AGENT_BROWSER_CDP_PORT:-9222}"
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

# show/hide restart this job; wait for the previous instance to release the
# profile before starting, then clear stale singleton artifacts.
for _ in $(seq 1 20); do
  pgrep -f "user-data-dir=$DATA_DIR" >/dev/null || break
  sleep 0.5
done
pkill -f "user-data-dir=$DATA_DIR" 2>/dev/null || true
rm -f "$DATA_DIR/SingletonLock" "$DATA_DIR/SingletonSocket" "$DATA_DIR/SingletonCookie"

MODE_ARGS=()
if [ -e "$DATA_DIR/.show" ]; then
  # Headed, for manual logins/2FA. --no-startup-window keeps launch from
  # activating the app; the operator brings a window up via `show`.
  MODE_ARGS+=(--no-startup-window)
else
  # Headless advertises "HeadlessChrome" in the UA, which some sites reject;
  # present the normal Chrome UA for this version instead.
  MAJOR="$("$CHROME_BIN" --version | grep -oE '[0-9]+' | head -1)"
  MODE_ARGS+=(
    --headless=new
    --window-size=1440,900
    --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${MAJOR}.0.0.0 Safari/537.36"
  )
fi

"$CHROME_BIN" \
  --user-data-dir="$DATA_DIR" \
  --profile-directory="$PROFILE" \
  --remote-debugging-port="$PORT" \
  --no-first-run \
  --no-default-browser-check \
  --hide-crash-restore-bubble \
  --disable-session-crashed-bubble \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  "${MODE_ARGS[@]}" &
CHROME_PID=$!

for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done

if [ -e "$DATA_DIR/.show" ]; then
  # Headed mode: restart the sentinel if it ever dies while Chrome is alive.
  while kill -0 "$CHROME_PID" 2>/dev/null; do
    "$NODE_BIN" "$BASE_DIR/scripts/sentinel.mjs" || true
    sleep 1
  done
else
  wait "$CHROME_PID"
fi
