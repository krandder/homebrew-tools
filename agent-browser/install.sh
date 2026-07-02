#!/bin/bash
# Install the agent browser: an always-running, always-hidden Chrome instance
# that AI agents drive over the DevTools protocol (CDP) without ever stealing
# focus or painting on your screen.
#
# Usage:
#   ./install.sh            # install to ~/agent-browser, sync Profile 2, load
#   AGENT_BROWSER_PROFILE="Profile 1" ./install.sh
set -euo pipefail

PREFIX="${AGENT_BROWSER_PREFIX:-$HOME/agent-browser}"
PROFILE="${AGENT_BROWSER_PROFILE:-Default}"
PORT="${AGENT_BROWSER_CDP_PORT:-9222}"
LABEL="com.agent-browser"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
NODE_BIN="$(command -v node || echo /opt/homebrew/bin/node)"

command -v node >/dev/null || { echo "node is required (brew install node)"; exit 1; }
[ -d "/Applications/Google Chrome.app" ] || { echo "Google Chrome not found"; exit 1; }

mkdir -p "$PREFIX/scripts" "$PREFIX/logs"
cp "$SRC_DIR/run.sh" "$SRC_DIR/sync-profile.sh" "$SRC_DIR/show" "$SRC_DIR/hide" "$PREFIX/"
cp "$SRC_DIR/scripts/sentinel.mjs" "$SRC_DIR/scripts/winctl.mjs" "$PREFIX/scripts/"
chmod +x "$PREFIX"/*.sh "$PREFIX/show" "$PREFIX/hide"

# playwright-core drives CDP for the sentinel + winctl.
( cd "$PREFIX" && [ -f package.json ] || npm init -y >/dev/null 2>&1; npm install playwright-core >/dev/null 2>&1 )

sed -e "s|__PREFIX__|$PREFIX|g" "$SRC_DIR/com.agent-browser.plist.template" > "$PLIST"

# Persist the runtime knobs the scripts read (profile, port, node path).
cat > "$PREFIX/env" <<EOF
export AGENT_BROWSER_DATA_DIR="\$HOME/.agent-chrome"
export AGENT_BROWSER_PROFILE="$PROFILE"
export AGENT_BROWSER_CDP_PORT="$PORT"
export AGENT_BROWSER_NODE="$NODE_BIN"
EOF

echo "Syncing Chrome '$PROFILE' into the agent browser..."
AGENT_BROWSER_PROFILE="$PROFILE" AGENT_BROWSER_CDP_PORT="$PORT" "$PREFIX/sync-profile.sh"

echo
echo "Installed to $PREFIX. The hidden agent browser is running on CDP port $PORT."
echo "Point any CDP client at http://127.0.0.1:$PORT — e.g. Playwright MCP:"
echo "  claude mcp add --scope user agent-browser -- npx -y @playwright/mcp@latest --cdp-endpoint http://127.0.0.1:$PORT"
echo "Manual access: $PREFIX/show  (then)  $PREFIX/hide"
echo "Refresh auth after a session expires: $PREFIX/sync-profile.sh"
