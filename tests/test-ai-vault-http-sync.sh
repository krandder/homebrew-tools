#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
PORT=$((24000 + $$ % 10000))
server_pid=""
cleanup() {
    [ -z "$server_pid" ] || kill "$server_pid" 2>/dev/null || true
    [ -z "$server_pid" ] || wait "$server_pid" 2>/dev/null || true
    rm -rf "$TMP"
}
trap cleanup EXIT

mkdir -p "$TMP/bin" "$TMP/vault"
cat > "$TMP/bin/ai-vault" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$AI_VAULT_ARGS"
cat > "$AI_VAULT_BODY"
echo ok >&2
SH
chmod +x "$TMP/bin/ai-vault"

python3 - "$TMP/vault/tokens.json" <<'PY'
import hashlib, json, sys
json.dump({hashlib.sha256(b"test-vault-token").hexdigest(): "adriana"}, open(sys.argv[1], "w"))
PY

AI_VAULT_ARGS="$TMP/args" AI_VAULT_BODY="$TMP/body" \
CODEX_VAULT_DIR="$TMP/vault" CODEX_VAULT_LISTEN="127.0.0.1:$PORT" \
PATH="$TMP/bin:$PATH" python3 "$ROOT/ai-vault-http" >"$TMP/server.log" 2>&1 &
server_pid=$!

for _ in 1 2 3 4 5; do
    /usr/bin/curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
    sleep 0.1
done
/usr/bin/curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null

post() {
    /usr/bin/curl -fsS -H "Authorization: Bearer test-vault-token" \
        --data-binary '{"credential":"fixture"}' "http://127.0.0.1:$PORT$1" >/dev/null
}

post /sync/claude/adriana
[ "$(cat "$TMP/args")" = "sync-receive claude:adriana" ]
grep -q '"credential":"fixture"' "$TMP/body"

post /push/claude/adriana
[ "$(cat "$TMP/args")" = "receive claude:adriana" ]

code="$(/usr/bin/curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer test-vault-token" \
    --data-binary '{}' "http://127.0.0.1:$PORT/sync/codex/adriana")"
[ "$code" = 400 ]

echo "ok: HTTP sync is additive and legacy push is unchanged"
