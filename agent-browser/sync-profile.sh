#!/bin/bash
# Sync the real Chrome profile into the agent browser's user-data-dir.
# The agent Chrome instance must not be running while its sqlite files are
# replaced, so this stops the LaunchAgent, syncs, and starts it again.
set -euo pipefail

SRC="${AGENT_BROWSER_SRC:-$HOME/Library/Application Support/Google/Chrome}"
DST="${AGENT_BROWSER_DATA_DIR:-$HOME/.agent-chrome}"
PROFILE="${AGENT_BROWSER_PROFILE:-Profile 2}"
LABEL="com.operator.agent-browser"

if [ ! -d "$SRC/$PROFILE" ]; then
  echo "source profile not found: $SRC/$PROFILE" >&2
  exit 1
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
# Give Chrome a moment to release its locks.
for _ in $(seq 1 20); do
  pgrep -f "user-data-dir=$DST" >/dev/null || break
  sleep 0.5
done
pkill -f "user-data-dir=$DST" 2>/dev/null || true

mkdir -p "$DST"
# Caches are excluded: they are large and carry no auth state.
rsync -a --delete \
  --exclude 'Cache/' \
  --exclude 'Code Cache/' \
  --exclude 'GPUCache/' \
  --exclude 'DawnGraphiteCache/' \
  --exclude 'DawnWebGPUCache/' \
  --exclude 'Service Worker/' \
  --exclude 'File System/' \
  --exclude 'IndexedDB/' \
  --exclude 'optimization_guide_model_store/' \
  "$SRC/$PROFILE/" "$DST/$PROFILE/"
cp "$SRC/Local State" "$DST/Local State"
touch "$DST/First Run"
# Drop stale singleton artifacts from a previous run of the agent instance.
rm -f "$DST/SingletonLock" "$DST/SingletonSocket" "$DST/SingletonCookie"

launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$LABEL.plist" 2>/dev/null ||
  launchctl kickstart -k "gui/$(id -u)/$LABEL"
echo "synced '$PROFILE' -> $DST and restarted agent browser"
