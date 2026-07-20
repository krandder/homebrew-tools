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
if [ "$*" = "authorize-pull claude:owner-b" ]; then
    echo denied >&2
    exit 1
fi
echo ok >&2
SH
chmod +x "$TMP/bin/ai-vault"

python3 - "$TMP/vault/tokens.json" <<'PY'
import hashlib, json, sys
json.dump({hashlib.sha256(b"test-vault-token").hexdigest(): "owner-a"}, open(sys.argv[1], "w"))
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
        -H "X-Ai-Token-Version: 3.0.3" \
        --data-binary '{"credential":"fixture"}' "http://127.0.0.1:$PORT$1" >/dev/null
}

post /sync/claude/owner-a
[ "$(cat "$TMP/args")" = "sync-receive claude:owner-a" ]
grep -q '"credential":"fixture"' "$TMP/body"

post /push/claude/owner-a
[ "$(cat "$TMP/args")" = "receive claude:owner-a" ]

code="$(/usr/bin/curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer test-vault-token" \
    -H "X-Ai-Token-Version: 3.0.3" \
    --data-binary '{}' "http://127.0.0.1:$PORT/sync/codex/owner-a")"
[ "$code" = 400 ]

code="$(/usr/bin/curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer test-vault-token" \
    --data-binary 'grant_type=refresh_token&refresh_token=vlt:owner-b:probe' \
    "http://127.0.0.1:$PORT/v1/oauth/token")"
[ "$code" = 403 ]
[ "$(cat "$TMP/args")" = "authorize-pull claude:owner-b" ]

mkdir -p "$TMP/home/.claude-profiles/owner-a/.claude"
cat > "$TMP/home/.claude-profiles/owner-a/.claude/credentials.json" <<'JSON'
{"claudeAiOauth":{"accessToken":"access","refreshToken":"owner-refresh"},"claudeTokenSync":{"refreshAuthority":"owner"}}
JSON
AI_TOKEN_BIN="$ROOT/ai-token" CODEX_VAULT_DIR="$TMP/vault" \
HOME="$TMP/home" python3 - "$ROOT/ai-vault-http" <<'PY'
import importlib.machinery, json, pathlib, types, sys

module = types.ModuleType("ai_vault_http")
importlib.machinery.SourceFileLoader(module.__name__, sys.argv[1]).exec_module(module)
try:
    module.broker_refresh("owner-a")
except RuntimeError:
    events = [json.loads(line) for line in pathlib.Path(module.HTTP_EVENTS_FILE).read_text().splitlines()]
    assert events[-1]["status"] == "failed"
    assert "owner-managed" in events[-1]["detail"]
else:
    raise AssertionError("owner-managed refresh reached the broker")
PY

echo "ok: HTTP sync is additive, broker refresh is ACL-gated, and owner refresh stays local"
