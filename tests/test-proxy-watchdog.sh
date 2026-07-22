#!/usr/bin/env bash
# Tests for bin/proxy-watchdog.sh — fully offline.
#
# curl / launchctl / systemctl / sleep are mocks placed earlier in PATH; the
# watchdog's unbounded loop is bounded by a counted sleep mock that kills the
# watchdog (its parent) after N passes, which makes restart counts exact.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WATCHDOG="$ROOT/bin/proxy-watchdog.sh"
[ -f "$WATCHDOG" ] || { echo "FAIL: $WATCHDOG does not exist" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
MOCKBIN="$TMP/mockbin"
mkdir -p "$MOCKBIN"

# curl mock: fail the first $CURL_FAILS calls, succeed after that
cat > "$MOCKBIN/curl" <<'EOF'
#!/usr/bin/env bash
n=$(cat "$CURL_STATE" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$CURL_STATE"
[ "$n" -le "${CURL_FAILS:-0}" ] && exit 7
echo '{"ok":true,"inflight":0}'
EOF

# launchctl mock: record every invocation
cat > "$MOCKBIN/launchctl" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$LAUNCHCTL_LOG"
EOF

# systemctl mock: --user works; record restarts
cat > "$MOCKBIN/systemctl" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-} ${2:-}" = "--user show-environment" ]; then exit 0; fi
if [ "${1:-} ${2:-}" = "--user restart" ]; then echo "restart ${3:-}" >> "$SYSTEMCTL_LOG"; exit 0; fi
exit 1
EOF

# counted sleep: instant, and kill the watchdog (our parent) after N passes
cat > "$MOCKBIN/sleep" <<'EOF'
#!/usr/bin/env bash
n=$(cat "$SLEEP_STATE" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$SLEEP_STATE"
if [ "$n" -ge "${SLEEP_KILL_AT:-999}" ]; then kill "$PPID" 2>/dev/null || true; fi
EOF
chmod +x "$MOCKBIN"/*

export CURL_STATE="$TMP/curl-state" SLEEP_STATE="$TMP/sleep-state"
export LAUNCHCTL_LOG="$TMP/launchctl.log" SYSTEMCTL_LOG="$TMP/systemctl.log"
export PATH="$MOCKBIN:$PATH"
URL="http://127.0.0.1:1/healthz"   # never really fetched: curl is mocked

fail() { echo "FAIL: $*" >&2; exit 1; }
reset_state() { rm -f "$CURL_STATE" "$SLEEP_STATE" "$LAUNCHCTL_LOG" "$SYSTEMCTL_LOG"; }
kicks() { [ -f "$LAUNCHCTL_LOG" ] && grep -c 'kickstart' "$LAUNCHCTL_LOG" || echo 0; }

# 1. transient failures then healthy: exactly one kickstart, right target,
#    log lines on stderr
reset_state
CURL_FAILS=2 SLEEP_KILL_AT=3 bash "$WATCHDOG" claude-any-proxy "$URL" 2 \
    2>"$TMP/stderr.log" || true
[ "$(kicks)" = 1 ] || fail "transient case: expected 1 kickstart, got $(kicks)"
grep -q "kickstart -k gui/$(id -u)/claude-any-proxy" "$LAUNCHCTL_LOG" \
    || fail "transient case: wrong kickstart target: $(cat "$LAUNCHCTL_LOG")"
grep -q 'proxy-watchdog: health check failed' "$TMP/stderr.log" \
    || fail "watchdog must log failures to stderr"

# 2. wedged (curl always fails): exactly one kickstart after 2 failures
reset_state
CURL_FAILS=999 SLEEP_KILL_AT=2 bash "$WATCHDOG" claude-any-proxy "$URL" 2 \
    2>/dev/null || true
[ "$(kicks)" = 1 ] || fail "wedged case: expected exactly 1 kickstart after 2 failures, got $(kicks)"

# 3. healthy: zero restarts
reset_state
CURL_FAILS=0 SLEEP_KILL_AT=2 bash "$WATCHDOG" claude-any-proxy "$URL" 2 \
    2>/dev/null || true
[ "$(kicks)" = 0 ] || fail "healthy case: expected zero restarts, got $(kicks)"

# 4. --once: single pass, exit 0 — both when healthy and when a restart fires
reset_state
CURL_FAILS=0 bash "$WATCHDOG" --once claude-any-proxy "$URL" 2 2>/dev/null \
    || fail "--once healthy must exit 0"
[ "$(kicks)" = 0 ] || fail "--once healthy must not restart"
reset_state
CURL_FAILS=999 bash "$WATCHDOG" --once claude-any-proxy "$URL" 1 2>/dev/null \
    || fail "--once wedged must exit 0"
[ "$(kicks)" = 1 ] || fail "--once wedged (max-failures=1) must restart exactly once"

# 5. no launchctl in PATH -> systemctl --user restart (scrubbed PATH: only the
#    tools the watchdog and its mocks need, so a real launchctl can't leak in)
SCRUB="$TMP/scrubbin"
mkdir -p "$SCRUB"
cp "$MOCKBIN/curl" "$MOCKBIN/systemctl" "$MOCKBIN/sleep" "$SCRUB/"
ln -s "$(command -v bash)" "$SCRUB/bash"
ln -s "$(command -v cat)" "$SCRUB/cat"
reset_state
PATH="$SCRUB" CURL_FAILS=999 SLEEP_KILL_AT=2 bash "$WATCHDOG" ai-token-any-proxy.service "$URL" 2 \
    2>/dev/null || true
[ -f "$SYSTEMCTL_LOG" ] || fail "systemd case: systemctl restart was never called"
[ "$(grep -c 'restart ai-token-any-proxy.service' "$SYSTEMCTL_LOG")" = 1 ] \
    || fail "systemd case: expected one 'restart ai-token-any-proxy.service', got: $(cat "$SYSTEMCTL_LOG")"
[ ! -f "$LAUNCHCTL_LOG" ] || fail "systemd case: launchctl must not be used"

echo "ok: proxy-watchdog"
