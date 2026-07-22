#!/usr/bin/env bash
# claude-any-probe — semantic health probe for the local any-proxy.
#
#   claude-any-probe.sh <port> [timeout_s=2]
#
# Exit 0 only when http://127.0.0.1:<port>/healthz answers HTTP 200 within
# <timeout_s> with a JSON body whose "ok" is true. Anything else exits 1
# with a one-line reason on stderr: connection refused, timeout, non-200,
# ok not true, or invalid JSON. Exit 2 on usage errors.
#
# Why this exists (2026-07-22 incident): the old wrapper health check was a
# bare TCP open — (exec 3<>/dev/tcp/127.0.0.1/PORT) — which is blind to a
# hung process holding a healthy LISTEN socket. A wrapper routing traffic to
# the any-proxy MUST gate on this probe, never on a transport-level check.
set -u

PROG="claude-any-probe"
PORT="${1:-}"
TIMEOUT="${2:-2}"

usage() { echo "usage: $PROG.sh <port> [timeout_s=2]" >&2; exit 2; }
fail()  { echo "$PROG: $*" >&2; exit 1; }

case "$PORT" in ''|*[!0-9]*) usage ;; esac
case "$TIMEOUT" in ''|*[!0-9]*|0*) usage ;; esac

# Fail closed: anything that prevents proving health is "unhealthy".
command -v curl >/dev/null 2>&1    || fail "curl not found; cannot prove health, failing closed"
command -v python3 >/dev/null 2>&1 || fail "python3 not found; cannot prove health, failing closed"

ERR="$(mktemp)"
trap 'rm -f "$ERR"' EXIT

OUT="$(curl -sS --max-time "$TIMEOUT" -w '\n%{http_code}' \
    "http://127.0.0.1:$PORT/healthz" 2>"$ERR")" || {
    rc=$?
    if [ "$rc" = 28 ]; then
        fail "no /healthz answer within ${TIMEOUT}s (hung listener: transport open, semantics dead)"
    fi
    detail="$(head -n 1 "$ERR")"
    fail "connection failed: ${detail:-curl exit $rc}"
}

CODE="${OUT##*$'\n'}"
BODY="${OUT%$'\n'*}"
[ "$CODE" = "200" ] || fail "/healthz answered HTTP ${CODE:-unknown}, want 200"

REASON="$(printf '%s' "$BODY" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("invalid JSON")
    raise SystemExit(1)
if isinstance(data, dict) and data.get("ok") is True:
    raise SystemExit(0)
print("ok is not true")
raise SystemExit(1)
')" || fail "/healthz 200 but $REASON"

exit 0
