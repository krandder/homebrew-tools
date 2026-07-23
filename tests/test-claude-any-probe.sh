#!/usr/bin/env bash
# Tests for bin/claude-any-probe.sh — the semantic any-proxy health probe.
#
# Fully offline: fake listeners are local python one-shot servers bound to
# ephemeral loopback ports. The probe must answer "healthy" ONLY for a 200
# /healthz with {"ok":true}; every other shape (blackhole, closed port,
# ok:false, garbage body) must exit 1 with a one-line stderr reason.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROBE="$ROOT/bin/claude-any-probe.sh"
[ -f "$PROBE" ] || { echo "FAIL: $PROBE does not exist" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
now_ms() { date +%s%N; }

# Fake /healthz: always 200, body depends on mode (ok / okfalse / garbage).
cat > "$TMP/healthz_server.py" <<'EOF'
import http.server
import sys

BODY = {
    "ok": b'{"ok":true,"inflight":0}',
    "okfalse": b'{"ok":false,"inflight":3}',
    "garbage": b"this is not json at all {{{",
}[sys.argv[1]]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, *_args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
print(server.server_port, flush=True)
server.serve_forever()
EOF

# Blackhole: LISTEN is open (the kernel completes handshakes into the accept
# backlog) but userspace never accept(2)s, so no byte is ever answered. This
# is the exact 2026-07-22 wedge shape: hung process, healthy-looking socket.
cat > "$TMP/blackhole.py" <<'EOF'
import socket
import time

listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("127.0.0.1", 0))
listener.listen(8)
print(listener.getsockname()[1], flush=True)
while True:
    time.sleep(3600)
EOF

wait_port_file() { # file -> port on stdout
    local deadline=$(( $(date +%s) + 10 ))
    while [ ! -s "$1" ]; do
        [ "$(date +%s)" -lt "$deadline" ] || fail "fake listener did not start ($1)"
        sleep 0.05
    done
    cat "$1"
}

one_line() { # file — assert exactly one stderr line
    [ "$(wc -l < "$1")" = 1 ] || fail "expected a one-line stderr reason, got: $(cat "$1")"
}

# a) healthy /healthz -> exit 0
python3 "$TMP/healthz_server.py" ok > "$TMP/port.ok" &
OK_PORT="$(wait_port_file "$TMP/port.ok")"
bash "$PROBE" "$OK_PORT" 2 >"$TMP/out.a" 2>"$TMP/err.a" \
    || fail "a) healthy /healthz must exit 0 (stderr: $(cat "$TMP/err.a"))"

# b) blackhole listener -> exit 1 within timeout+2s (THE blindness regression)
python3 "$TMP/blackhole.py" > "$TMP/port.bh" &
BH_PORT="$(wait_port_file "$TMP/port.bh")"
start="$(now_ms)"
rc_new=0
bash "$PROBE" "$BH_PORT" 1 2>"$TMP/err.b" || rc_new=$?
elapsed_ms=$(( ($(now_ms) - start) / 1000000 ))
[ "$rc_new" = 1 ] || fail "b) probe must exit 1 against a hung listener (got $rc_new)"
[ "$elapsed_ms" -lt 3000 ] || fail "b) probe took ${elapsed_ms}ms; must fail within timeout+2s"
one_line "$TMP/err.b"
# 2026-07-22 incident contrast — this is what makes the test non-vacuous.
# The OLD wrapper health check was a bare TCP open ((exec 3<>/dev/tcp/...)):
# against the same hung-but-listening blackhole it SUCCEEDS, i.e. it is blind
# to the wedge. Assert the contrast explicitly: old = blind (0), new = caught (1).
rc_old=0
(exec 3<>"/dev/tcp/127.0.0.1/$BH_PORT") 2>/dev/null || rc_old=$?
[ "$rc_old" = 0 ] \
    || fail "b) contrast premise broken: the old TCP-open check should be BLIND (exit 0) against the blackhole, got $rc_old"
[ "$rc_new" = 1 ] && [ "$rc_old" = 0 ] \
    || fail "b) blindness contrast failed: old=$rc_old (want 0/blind), new=$rc_new (want 1/caught)"
echo "ok: blindness contrast — old TCP-open blind ($rc_old), semantic probe caught the wedge ($rc_new)"

# c) closed port (nothing listening) -> exit 1 fast: with a generous 10s
#    timeout the refusal must still return immediately, not wait it out.
CLOSED_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
start="$(now_ms)"
rc=0
bash "$PROBE" "$CLOSED_PORT" 10 2>"$TMP/err.c" || rc=$?
elapsed_ms=$(( ($(now_ms) - start) / 1000000 ))
[ "$rc" = 1 ] || fail "c) closed port must exit 1 (got $rc)"
[ "$elapsed_ms" -lt 5000 ] \
    || fail "c) closed port took ${elapsed_ms}ms with a 10s timeout — refusal must be fast"
one_line "$TMP/err.c"

# d) /healthz 200 but {"ok":false} -> exit 1
python3 "$TMP/healthz_server.py" okfalse > "$TMP/port.false" &
FALSE_PORT="$(wait_port_file "$TMP/port.false")"
rc=0
bash "$PROBE" "$FALSE_PORT" 2 2>"$TMP/err.d" || rc=$?
[ "$rc" = 1 ] || fail "d) ok:false must exit 1 (got $rc)"
one_line "$TMP/err.d"

# e) /healthz 200 with a garbage (non-JSON) body -> exit 1
python3 "$TMP/healthz_server.py" garbage > "$TMP/port.garbage" &
GARBAGE_PORT="$(wait_port_file "$TMP/port.garbage")"
rc=0
bash "$PROBE" "$GARBAGE_PORT" 2 2>"$TMP/err.e" || rc=$?
[ "$rc" = 1 ] || fail "e) garbage 200 must exit 1 (got $rc)"
one_line "$TMP/err.e"

echo "ok: claude-any-probe"
