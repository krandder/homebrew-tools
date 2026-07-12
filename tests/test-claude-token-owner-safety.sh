#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
cat > "$TMP/bin/uname" <<'SH'
#!/usr/bin/env bash
echo Linux
SH
cat > "$TMP/bin/claude-real" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = auth ] && [ "${2:-}" = login ]; then
    [ -z "${CLAUDE_LOGIN_CREDS:-}" ] || cp "$CLAUDE_LOGIN_CREDS" "$HOME/.claude/.credentials.json"
    exit "${CLAUDE_LOGIN_STATUS:-0}"
fi
printf '%s\n' "${ANTHROPIC_AUTH_TOKEN-unset}" > "$TEST_OUTPUT"
printf '%s\n' "$*" >> "$TEST_OUTPUT"
SH
cat > "$TMP/bin/curl" <<'SH'
#!/usr/bin/env bash
printf called >> "$CURL_CALLED"
for arg in "$@"; do
    [ "$arg" = @/dev/stdin ] && cat > "$CURL_BODY"
done
[ -n "${CURL_RESPONSE:-}" ] && cat "$CURL_RESPONSE"
exit "${CURL_STATUS:-0}"
SH
cat > "$TMP/bin/sleep" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$TMP/bin/"*

new_home() {
    HOME="$TMP/$1"
    export HOME
    mkdir -p "$HOME/.claude-token" "$HOME/.claude" "$HOME/shared/claude-tokens"
    TEST_OUTPUT="$HOME/result" CURL_CALLED="$HOME/curl-called" CURL_BODY="$HOME/curl-body"
    CURL_STATUS=0 CURL_RESPONSE=""
    CLAUDE_LOGIN_STATUS=0 CLAUDE_LOGIN_CREDS=""
    export TEST_OUTPUT CURL_CALLED CURL_BODY CURL_STATUS CURL_RESPONSE CLAUDE_LOGIN_STATUS CLAUDE_LOGIN_CREDS
    printf 'user=adriana\nurl=https://vault.invalid\ntoken=test-token\n' > "$HOME/.claude-token/config"
    printf '%b' "${2:-}" >> "$HOME/.claude-token/config"
}

write_creds() {
    printf '{"claudeAiOauth":{"accessToken":"local-access","refreshToken":"%s","expiresAt":4102444800000}}\n' "$1" > "$HOME/.claude/.credentials.json"
}

write_shared() {
    local token="$1" expires="$2" path="${3:-$HOME/shared/claude-tokens/adriana.json}"
    printf '{"claudeAiOauth":{"accessToken":"%s","refreshToken":"__follower_no_refresh__","expiresAt":%s}}\n' "$token" "$expires" > "$path"
}

write_owner_snapshot() {
    local path="$1" token="$2" refresh="$3" expires="$4"
    printf '{"claudeAiOauth":{"accessToken":"%s","refreshToken":"%s","expiresAt":%s}}\n' "$token" "$refresh" "$expires" > "$path"
}

run_token() {
    PATH="$TMP/bin:$PATH" CLAUDE_REAL_BIN="$TMP/bin/claude-real" "$ROOT/claude-token" "$@"
}

# Explicit owner mode must never consult the vault, even before login or after logout.
new_home owner 'mode=owner\n'
CURL_STATUS=99; export CURL_STATUS
run_token run hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = unset ]
[ ! -e "$CURL_CALLED" ]

# Auto mode preserves native Claude when a real local refresh token is present.
new_home auto
write_creds real-refresh-token
run_token run hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = unset ]
[ ! -e "$CURL_CALLED" ]

# Credential reality wins even if follower mode was configured accidentally.
new_home follower-with-owner 'mode=follower\n'
write_creds real-refresh-token
run_token run hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = unset ]
[ ! -e "$CURL_CALLED" ]

# Pull cannot replace owner credentials, and stale follower pulls never write.
new_home owner-pull 'mode=owner\n'
write_creds owner-refresh
before="$(shasum -a 256 "$HOME/.claude/.credentials.json")"
if run_token pull --profile adriana >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected owner pull to be refused" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$HOME/.claude/.credentials.json")" ]

new_home follower-owner-pull 'mode=follower\n'
write_creds owner-refresh
before="$(shasum -a 256 "$HOME/.claude/.credentials.json")"
if run_token pull --profile adriana >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected follower mode not to override owner credentials" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$HOME/.claude/.credentials.json")" ]

new_home stale-pull 'mode=follower\n'
write_creds __follower_no_refresh__
write_shared stale-token 1
CURL_RESPONSE="$HOME/remote.json"; export CURL_RESPONSE
write_shared remote-stale-token 1 "$CURL_RESPONSE"
before="$(shasum -a 256 "$HOME/.claude/.credentials.json")"
if run_token pull --profile adriana >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected stale follower pull to fail" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$HOME/.claude/.credentials.json")" ]

# Followers accept an opaque access token only when expiresAt proves it is fresh.
new_home fresh 'mode=follower\n'
write_creds __follower_no_refresh__
write_shared fresh-opaque-token 4102444800000
run_token run hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = fresh-opaque-token ]
[ ! -e "$CURL_CALLED" ]

# A stale local token may be replaced by a fresh, freshness-validated vault pull.
new_home remote 'mode=follower\n'
write_creds __follower_no_refresh__
write_shared stale-token 1
CURL_RESPONSE="$HOME/remote.json"; export CURL_RESPONSE
write_shared remote-fresh-token 4102444800000 "$CURL_RESPONSE"
run_token run hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = remote-fresh-token ]
[ -e "$CURL_CALLED" ]

# Stale data from both sources fails clearly and never starts Claude with bad auth.
new_home stale 'mode=follower\n'
write_creds __follower_no_refresh__
write_shared stale-token 1
CURL_RESPONSE="$HOME/remote.json"; export CURL_RESPONSE
write_shared remote-stale-token 1 "$CURL_RESPONSE"
if run_token run hello >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected stale follower launch to fail" >&2
    exit 1
fi
grep -q "no fresh follower token" "$HOME/stderr"
[ ! -e "$TEST_OUTPUT" ]

# Sync copies owner credentials without altering the local file.
new_home sync 'mode=owner\n'
write_creds real-refresh-token
before="$(shasum -a 256 "$HOME/.claude/.credentials.json")"
run_token sync --profile adriana
[ "$before" = "$(shasum -a 256 "$HOME/.claude/.credentials.json")" ]
grep -q real-refresh-token "$CURL_BODY"

# Native login remains successful when vault sync is unavailable, and a failed
# native login is returned unchanged without contacting the vault.
new_home login 'mode=owner\n'
CLAUDE_LOGIN_CREDS="$HOME/new-creds.json" CURL_STATUS=22
export CLAUDE_LOGIN_CREDS CURL_STATUS
write_shared ignored 4102444800000 "$CLAUDE_LOGIN_CREDS"
python3 - "$CLAUDE_LOGIN_CREDS" <<'PY'
import json, sys
p=sys.argv[1]; d=json.load(open(p)); d["claudeAiOauth"]["refreshToken"]="new-real-refresh"; json.dump(d,open(p,"w"))
PY
run_token login
grep -q new-real-refresh "$HOME/.claude/.credentials.json"
[ -e "$CURL_CALLED" ]

new_home login-fails 'mode=owner\n'
CLAUDE_LOGIN_STATUS=7; export CLAUDE_LOGIN_STATUS
if run_token login >/dev/null 2>&1; then
    echo "expected native login status to propagate" >&2
    exit 1
else
    [ "$?" -eq 7 ]
fi
[ ! -e "$CURL_CALLED" ]

# Browser login remains a local recovery path before vault configuration.
new_home login-unconfigured
rm -f "$HOME/.claude-token/config"
CLAUDE_LOGIN_CREDS="$HOME/new-creds.json"; export CLAUDE_LOGIN_CREDS
write_owner_snapshot "$CLAUDE_LOGIN_CREDS" local-access local-refresh 4102444800000
run_token login >"$HOME/stdout" 2>"$HOME/stderr"
grep -q local-refresh "$HOME/.claude/.credentials.json"
grep -q "vault sync skipped" "$HOME/stderr"
[ ! -e "$CURL_CALLED" ]

# Bare pairing uses auto mode, which protects a real local refresh token while
# remaining follower-compatible when no local owner login exists.
new_home pair-auto
rm -f "$HOME/.claude-token/config"
CURL_RESPONSE="$HOME/approved.json"; export CURL_RESPONSE
printf '{"status":"approved","token":"paired-token","user":"adriana"}\n' > "$CURL_RESPONSE"
run_token pair --user adriana >/dev/null
grep -q '^mode=auto$' "$HOME/.claude-token/config"
[ -x "$HOME/bin/claude" ]

new_home pair-auto-owner
write_creds real-refresh-token
CURL_RESPONSE="$HOME/approved.json"; export CURL_RESPONSE
printf '{"status":"approved","token":"paired-token","user":"adriana"}\n' > "$CURL_RESPONSE"
run_token pair --user adriana >/dev/null
grep -q '^mode=auto$' "$HOME/.claude-token/config"
[ ! -e "$HOME/bin/claude" ]

# The vault never serves an expired Claude access token.
VAULT="$TMP/vault"
mkdir -p "$VAULT/state" "$VAULT/shared" "$VAULT/profiles"
printf '{"operator":"adriana","admins":[],"profiles":{"claude:adriana":{"owner":"adriana","pullers":["adriana"],"kind":"claude"}}}\n' > "$VAULT/state/acl.json"
write_shared stale-token 1 "$VAULT/shared/adriana.json"
if CODEX_VAULT_USER=adriana CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" access claude:adriana >/dev/null 2>&1; then
    echo "expected vault to reject stale access" >&2
    exit 1
fi
if CODEX_VAULT_USER=adriana CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" serve claude:adriana >/dev/null 2>&1; then
    echo "expected vault to reject stale pulls" >&2
    exit 1
fi
write_shared vault-fresh-token 4102444800000 "$VAULT/shared/adriana.json"
[ "$(CODEX_VAULT_USER=adriana CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" access claude:adriana)" = vault-fresh-token ]
CODEX_VAULT_USER=adriana CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" serve claude:adriana | grep -q vault-fresh-token

vault_cmd() {
    CODEX_VAULT_USER=adriana CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" "$@"
}

# Owner sync is atomic, does not refresh, and rejects stale or conflicting
# rotations without replacing the last accepted canonical credential.
FIRST="$VAULT/first.json" STALE="$VAULT/stale.json" CONFLICT="$VAULT/conflict.json" NEWER="$VAULT/newer.json"
write_owner_snapshot "$FIRST" first-access first-refresh 4102444800000
vault_cmd sync-receive claude:adriana < "$FIRST"
canonical="$VAULT/profiles/adriana/.claude/credentials.json"
grep -q first-refresh "$canonical"
grep -q '"refreshAuthority": "owner"' "$canonical"
grep -q __follower_no_refresh__ "$VAULT/shared/adriana.json"

write_owner_snapshot "$STALE" stale-access stale-refresh 4102444700000
before="$(shasum -a 256 "$canonical")"
if vault_cmd sync-receive claude:adriana < "$STALE" >/dev/null 2>&1; then
    echo "expected stale owner sync to fail" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$canonical")" ]

write_owner_snapshot "$CONFLICT" conflict-access conflict-refresh 4102444800000
if vault_cmd sync-receive claude:adriana < "$CONFLICT" >/dev/null 2>&1; then
    echo "expected conflicting owner sync to fail" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$canonical")" ]

write_owner_snapshot "$NEWER" newer-access newer-refresh 4102444900000
vault_cmd sync-receive claude:adriana < "$NEWER"
grep -q newer-refresh "$canonical"

# Concurrent arrivals serialize; the greatest expiry wins regardless of order.
LOW="$VAULT/low.json" HIGH="$VAULT/high.json"
write_owner_snapshot "$LOW" low-access low-refresh 4102445000000
write_owner_snapshot "$HIGH" high-access high-refresh 4102445100000
vault_cmd sync-receive claude:adriana < "$LOW" >/dev/null 2>&1 & low_pid=$!
vault_cmd sync-receive claude:adriana < "$HIGH" >/dev/null 2>&1 & high_pid=$!
wait "$low_pid" || true
wait "$high_pid" || true
grep -q high-refresh "$canonical"

# Owner-managed canonical files cannot be refreshed by a later vault publish.
python3 - "$canonical" <<'PY'
import json, sys
p=sys.argv[1]; d=json.load(open(p)); d["claudeAiOauth"]["expiresAt"]=1; json.dump(d,open(p,"w"))
PY
if HOME="$VAULT" CLAUDE_PROFILES_DIR="$VAULT/profiles" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_REAL_BIN="$TMP/bin/claude-real" "$ROOT/claude-token" publish --profile adriana >"$VAULT/publish-out" 2>"$VAULT/publish-err"; then
    echo "expected owner-managed vault publish to refuse refresh" >&2
    exit 1
fi
grep -q "owner-managed" "$VAULT/publish-err"

# Explicit owner mode refuses publish even for an unmarked local credential.
new_home owner-publish 'mode=owner\n'
mkdir -p "$HOME/.claude-profiles/adriana/.claude"
write_owner_snapshot "$HOME/.claude-profiles/adriana/.claude/credentials.json" access refresh 1
if run_token publish --profile adriana >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected publish to be disabled in owner mode" >&2
    exit 1
fi
grep -q "publish is disabled in owner mode" "$HOME/stderr"

echo "ok: owner safety and follower freshness"
