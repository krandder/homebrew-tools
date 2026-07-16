#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
cat > "$TMP/bin/uname" <<'SH'
#!/usr/bin/env bash
echo "${FAKE_UNAME:-Linux}"
SH
cat > "$TMP/bin/claude-real" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = auth ] && [ "${2:-}" = login ]; then
    [ -z "${CLAUDE_LOGIN_CREDS:-}" ] || cp "$CLAUDE_LOGIN_CREDS" "$HOME/.claude/.credentials.json"
    exit "${CLAUDE_LOGIN_STATUS:-0}"
fi
printf '%s\n' "${ANTHROPIC_AUTH_TOKEN-unset}" > "$TEST_OUTPUT"
printf '%s\n' "$*" >> "$TEST_OUTPUT"
printf '%s\n' "$HOME" >> "$TEST_OUTPUT"
printf '%s\n' "${CLAUDE_CODE_OAUTH_TOKEN-unset}" >> "$TEST_OUTPUT"
printf '%s\n' "${ANTHROPIC_API_KEY-unset}" >> "$TEST_OUTPUT"
printf '%s\n' "${CLAUDE_CONFIG_DIR-unset}" >> "$TEST_OUTPUT"
SH
cat > "$TMP/bin/curl" <<'SH'
#!/usr/bin/env bash
printf called >> "$CURL_CALLED"
for arg in "$@"; do
    case "$arg" in @/dev/stdin) cat > "$CURL_BODY";; @*) cat "${arg#@}" > "$CURL_BODY";; esac
done
[ -n "${CURL_RESPONSE:-}" ] && cat "$CURL_RESPONSE"
exit "${CURL_STATUS:-0}"
SH
cat > "$TMP/bin/crontab" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = -l ]; then
    [ -f "$CRONTAB_FILE" ] && cat "$CRONTAB_FILE"
else
    cat > "$CRONTAB_FILE"
fi
SH
cat > "$TMP/bin/launchctl" <<'SH'
#!/usr/bin/env bash
exit 0
SH
cat > "$TMP/bin/security" <<'SH'
#!/usr/bin/env bash
[ -z "${SECURITY_CALLED:-}" ] || printf called >> "$SECURITY_CALLED"
exit 99
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
    TEST_OUTPUT="$HOME/result" CURL_CALLED="$HOME/curl-called" CURL_BODY="$HOME/curl-body" SECURITY_CALLED="$HOME/security-called" CRONTAB_FILE="$HOME/crontab"
    CURL_STATUS=0 CURL_RESPONSE=""
    CLAUDE_LOGIN_STATUS=0 CLAUDE_LOGIN_CREDS=""
    FAKE_UNAME=Linux CLAUDE_TOKEN_WRAPPER_DIR="$HOME/bin" CLAUDE_TOKEN_MAINTENANCE_DIR="$HOME/LaunchAgents"
    unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CONFIG_DIR
    export TEST_OUTPUT CURL_CALLED CURL_BODY SECURITY_CALLED CRONTAB_FILE CURL_STATUS CURL_RESPONSE CLAUDE_LOGIN_STATUS CLAUDE_LOGIN_CREDS FAKE_UNAME CLAUDE_TOKEN_WRAPPER_DIR CLAUDE_TOKEN_MAINTENANCE_DIR
    printf 'user=owner-a\nurl=https://vault.invalid\ntoken=test-token\n' > "$HOME/.claude-token/config"
    printf '%b' "${2:-}" >> "$HOME/.claude-token/config"
}

write_creds() {
    printf '{"claudeAiOauth":{"accessToken":"local-access","refreshToken":"%s","expiresAt":4102444800000}}\n' "$1" > "$HOME/.claude/.credentials.json"
}

write_shared() {
    local token="$1" expires="$2" path="${3:-$HOME/shared/claude-tokens/owner-a.json}"
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

# Check distinguishes a locally recoverable owner from an unusable stale follower.
printf '{"claudeAiOauth":{"accessToken":"stale","refreshToken":"real-refresh-token","expiresAt":1}}\n' > "$HOME/.claude/.credentials.json"
run_token check > "$HOME/check"
grep -q "needs native refresh" "$HOME/check"
printf '{"claudeAiOauth":{"accessToken":"stale","refreshToken":"__follower_no_refresh__","expiresAt":1}}\n' > "$HOME/.claude/.credentials.json"
if run_token check > "$HOME/check"; then
    echo "expected stale follower check to fail" >&2
    exit 1
fi
grep -q "owner must sync fresh credentials" "$HOME/check"

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
if run_token pull --profile owner-a >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected owner pull to be refused" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$HOME/.claude/.credentials.json")" ]

new_home follower-owner-pull 'mode=follower\n'
write_creds owner-refresh
before="$(shasum -a 256 "$HOME/.claude/.credentials.json")"
if run_token pull --profile owner-a >"$HOME/stdout" 2>"$HOME/stderr"; then
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
if run_token pull --profile owner-a >"$HOME/stdout" 2>"$HOME/stderr"; then
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
run_token sync --profile owner-a
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
printf '{"status":"approved","token":"paired-token","user":"owner-a"}\n' > "$CURL_RESPONSE"
run_token pair --user owner-a >/dev/null
grep -q '^mode=auto$' "$HOME/.claude-token/config"
[ -x "$HOME/bin/claude" ]

new_home pair-auto-owner
write_creds real-refresh-token
CURL_RESPONSE="$HOME/approved.json"; export CURL_RESPONSE
printf '{"status":"approved","token":"paired-token","user":"owner-a"}\n' > "$CURL_RESPONSE"
run_token pair --user owner-a >/dev/null
grep -q '^mode=auto$' "$HOME/.claude-token/config"
[ ! -e "$HOME/bin/claude" ]

# Named followers share normal Claude HOME/state while account selection stays
# isolated in claude-token's follower config and fresh environment token.
new_home named-followers
FAKE_UNAME=Darwin; export FAKE_UNAME
for profile in operator owner-b; do
    mkdir -p "$HOME/.claude-token/followers/$profile"
    printf 'user=%s\nurl=https://vault.invalid\ntoken=%s-token\nmode=follower\n' "$profile" "$profile" > "$HOME/.claude-token/followers/$profile/config"
done
mkdir -p "$HOME/.claude-profiles/operator/.claude"
printf '{"theme":"dark","hasCompletedOnboarding":false}\n' > "$HOME/.claude-profiles/operator/.claude/.claude.json"
printf '{"theme":"dark","permissions":{"allow":["Read"]}}\n' > "$HOME/.claude-profiles/operator/.claude/settings.json"
ANTHROPIC_API_KEY=stale-api-key ANTHROPIC_AUTH_TOKEN=stale-shell-token CLAUDE_CODE_OAUTH_TOKEN=stale-shell-token
export ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN

CURL_RESPONSE="$HOME/operator.json"; export CURL_RESPONSE
write_shared operator-fresh-token 4102444800000 "$CURL_RESPONSE"
run_token run-follower operator hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = operator-fresh-token ]
[ "$(sed -n '2p' "$TEST_OUTPUT")" = hello ]
[ "$(sed -n '3p' "$TEST_OUTPUT")" = "$HOME" ]
[ "$(sed -n '4p' "$TEST_OUTPUT")" = operator-fresh-token ]
[ "$(sed -n '5p' "$TEST_OUTPUT")" = unset ]
[ "$(sed -n '6p' "$TEST_OUTPUT")" = unset ]
python3 - "$HOME/.claude-profiles/operator/.claude/.claude.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["hasCompletedOnboarding"] is False
assert d["theme"] == "dark"
PY
python3 - "$HOME/.claude-profiles/operator/.claude/settings.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["theme"] == "dark"
assert d["permissions"]["allow"] == ["Read"]
assert "defaultMode" not in d["permissions"]
PY
[ ! -e "$SECURITY_CALLED" ]

CURL_RESPONSE="$HOME/owner-b.json"; export CURL_RESPONSE
write_shared owner-b-fresh-token 4102444800000 "$CURL_RESPONSE"
run_token run-follower owner-b hello
[ "$(sed -n '1p' "$TEST_OUTPUT")" = owner-b-fresh-token ]
[ "$(sed -n '3p' "$TEST_OUTPUT")" = "$HOME" ]
[ ! -e "$SECURITY_CALLED" ]

rm -f "$TEST_OUTPUT"
if run_token run-follower operator auth login >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected named follower login to be refused" >&2
    exit 1
fi
grep -q "cannot change login state" "$HOME/stderr"
[ ! -e "$TEST_OUTPUT" ]
[ ! -e "$SECURITY_CALLED" ]

# One installed maintenance entry safely syncs owner credentials and reports
# the exact client version/host without changing the local refresh token.
new_home maintenance 'mode=owner\n'
write_creds real-refresh-token
run_token install-maintenance >/dev/null
grep -q 'claude-token-maintain$' "$CRONTAB_FILE"
grep -q ' maintain ' "$CRONTAB_FILE"
run_token maintain
python3 - "$CURL_BODY" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["tool"] == "claude-token"
assert d["version"] == "2.5.13"
assert d["profile"] == "owner-a"
assert d["mode"] == "owner"
assert d["status"] == "synced"
PY
python3 - "$HOME/.claude/.credentials.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1]))["claudeAiOauth"]["refreshToken"] == "real-refresh-token"
PY

# Pairing a named follower installs only claude-NAME and never inspects native
# credentials or replaces an existing plain Claude command.
new_home named-pair
FAKE_UNAME=Darwin; export FAKE_UNAME
mkdir -p "$HOME/bin"
printf 'keep-plain-claude\n' > "$HOME/bin/claude"
before="$(shasum -a 256 "$HOME/bin/claude")"
CURL_RESPONSE="$HOME/approved.json"; export CURL_RESPONSE
printf '{"status":"approved","token":"paired-token","user":"operator"}\n' > "$CURL_RESPONSE"
mkdir -p "$HOME/.claude-profiles/operator/.claude"
printf '{"theme":"dark","permissions":{"allow":["Read"]}}\n' > "$HOME/.claude-profiles/operator/.claude/settings.json"
run_token add-follower operator >/dev/null
[ "$before" = "$(shasum -a 256 "$HOME/bin/claude")" ]
[ -x "$HOME/bin/claude-operator" ]
grep -q 'run-follower "operator"' "$HOME/bin/claude-operator"
grep -q '^mode=follower$' "$HOME/.claude-token/followers/operator/config"
python3 - "$HOME/.claude-profiles/operator/.claude/settings.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["theme"] == "dark"
assert d["permissions"]["allow"] == ["Read"]
assert d["permissions"] == {"allow": ["Read"]}
PY
[ ! -e "$SECURITY_CALLED" ]
WRAPPER_OUTPUT="$HOME/wrapper-output"; export WRAPPER_OUTPUT
cat > "$TMP/bin/claude-token" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$WRAPPER_OUTPUT"
SH
chmod +x "$TMP/bin/claude-token"
PATH="$TMP/bin:$PATH" "$HOME/bin/claude-operator" hello
[ "$(cat "$WRAPPER_OUTPUT")" = "run-follower operator hello" ]

# An authorized main config can install a named follower without re-pairing.
new_home install-from-current
printf 'user=operator\nurl=https://vault.invalid\ntoken=current-token\n' > "$HOME/.claude-token/config"
printf 'export KEEP=this\nalias claude-operator='\''HOME=/tmp claude'\''\n' > "$HOME/.zshrc"
rm -f "$CURL_CALLED"
CLAUDE_TOKEN_FULL_PERMISSIONS=no run_token install-follower-wrapper operator >/dev/null
[ -x "$HOME/bin/claude-operator" ]
grep -q 'run-follower "operator"' "$HOME/bin/claude-operator"
grep -q '^user=operator$' "$HOME/.claude-token/followers/operator/config"
grep -q '^token=current-token$' "$HOME/.claude-token/followers/operator/config"
grep -q '^mode=follower$' "$HOME/.claude-token/followers/operator/config"
grep -q '^export KEEP=this$' "$HOME/.zshrc"
! grep -q 'alias claude-operator=' "$HOME/.zshrc"
ls "$HOME"/.zshrc.pre-claude-token.* >/dev/null
[ ! -e "$CURL_CALLED" ]

# An existing pairing can repair a stale wrapper without pairing again.
new_home named-pair-repair
mkdir -p "$HOME/.claude-token/followers/operator"
printf 'user=operator\nurl=https://vault.invalid\ntoken=operator-token\nmode=follower\n' > "$HOME/.claude-token/followers/operator/config"
mkdir -p "$HOME/bin" "$HOME/.claude-profiles/operator/.claude"
printf '{"theme":"dark","permissions":{"allow":["Read"]}}\n' > "$HOME/.claude-profiles/operator/.claude/settings.json"
printf 'legacy wrapper\n' > "$HOME/bin/claude-operator"
rm -f "$CURL_CALLED"
CLAUDE_TOKEN_FULL_PERMISSIONS=no PATH="$TMP/bin:$PATH" run_token install-follower-wrapper operator >/dev/null
grep -q 'run-follower "operator"' "$HOME/bin/claude-operator"
[ -e "$HOME/bin/claude-operator.pre-claude-token" ]
[ ! -e "$CURL_CALLED" ]
python3 - "$HOME/.claude-profiles/operator/.claude/settings.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["theme"] == "dark"
assert d["permissions"]["allow"] == ["Read"]
assert "defaultMode" not in d["permissions"]
assert "bypassPermissionsModeAccepted" not in d
PY

mkdir -p "$HOME/legacy-bin"
printf 'path-preferred legacy wrapper\n' > "$HOME/legacy-bin/claude-operator"
chmod +x "$HOME/legacy-bin/claude-operator"
CLAUDE_TOKEN_WRAPPER_DIR="" PATH="$HOME/legacy-bin:$PATH" run_token install-follower-wrapper operator >/dev/null
grep -q 'run-follower "operator"' "$HOME/legacy-bin/claude-operator"
[ -e "$HOME/legacy-bin/claude-operator.pre-claude-token" ]

printf 'stale generated wrapper\n' > "$HOME/bin/claude-operator"
rm -f "$CURL_CALLED"
run_token repair-follower-wrappers >/dev/null
grep -q 'run-follower "operator"' "$HOME/bin/claude-operator"
[ ! -e "$CURL_CALLED" ]

# Direct operator commands select the same canonical store as ai-vault-http,
# while installations with only the legacy directory remain compatible.
DEFAULT_HOME="$TMP/default-vault-home"
mkdir -p "$DEFAULT_HOME/.codex-vault" "$DEFAULT_HOME/.ai-vault"
printf '{"admins":["owner-a"],"profiles":{}}\n' > "$DEFAULT_HOME/.codex-vault/acl.json"
printf '{"admins":[],"profiles":{}}\n' > "$DEFAULT_HOME/.ai-vault/acl.json"
( unset CODEX_VAULT_DIR; HOME="$DEFAULT_HOME" CODEX_VAULT_USER=owner-a "$ROOT/ai-vault" list >/dev/null )

LEGACY_HOME="$TMP/legacy-vault-home"
mkdir -p "$LEGACY_HOME/.ai-vault"
printf '{"admins":["owner-a"],"profiles":{}}\n' > "$LEGACY_HOME/.ai-vault/acl.json"
( unset CODEX_VAULT_DIR; HOME="$LEGACY_HOME" CODEX_VAULT_USER=owner-a "$ROOT/ai-vault" list >/dev/null )

# The vault never serves an expired Claude access token.
VAULT="$TMP/vault"
mkdir -p "$VAULT/state" "$VAULT/shared" "$VAULT/profiles"
printf '{"operator":"owner-a","admins":[],"profiles":{"claude:owner-a":{"owner":"owner-a","pullers":["owner-a"],"kind":"claude"}}}\n' > "$VAULT/state/acl.json"
write_shared stale-token 1 "$VAULT/shared/owner-a.json"
if CODEX_VAULT_USER=owner-a CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" access claude:owner-a >/dev/null 2>&1; then
    echo "expected vault to reject stale access" >&2
    exit 1
fi
if CODEX_VAULT_USER=owner-a CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" serve claude:owner-a >/dev/null 2>&1; then
    echo "expected vault to reject stale pulls" >&2
    exit 1
fi
write_shared vault-fresh-token 4102444800000 "$VAULT/shared/owner-a.json"
[ "$(CODEX_VAULT_USER=owner-a CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" access claude:owner-a)" = vault-fresh-token ]
CODEX_VAULT_USER=owner-a CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" serve claude:owner-a | grep -q vault-fresh-token

vault_cmd() {
    CODEX_VAULT_USER=owner-a CODEX_VAULT_DIR="$VAULT/state" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_PROFILES_DIR="$VAULT/profiles" "$ROOT/ai-vault" "$@"
}

# Owner sync is atomic, does not refresh, and rejects stale or conflicting
# rotations without replacing the last accepted canonical credential.
FIRST="$VAULT/first.json" STALE="$VAULT/stale.json" CONFLICT="$VAULT/conflict.json" NEWER="$VAULT/newer.json"
write_owner_snapshot "$FIRST" first-access first-refresh 4102444800000
vault_cmd sync-receive claude:owner-a < "$FIRST"
canonical="$VAULT/profiles/owner-a/.claude/credentials.json"
grep -q first-refresh "$canonical"
grep -q '"refreshAuthority": "owner"' "$canonical"
grep -q __follower_no_refresh__ "$VAULT/shared/owner-a.json"

write_owner_snapshot "$STALE" stale-access stale-refresh 4102444700000
before="$(shasum -a 256 "$canonical")"
if vault_cmd sync-receive claude:owner-a < "$STALE" >/dev/null 2>&1; then
    echo "expected stale owner sync to fail" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$canonical")" ]

write_owner_snapshot "$CONFLICT" conflict-access conflict-refresh 4102444800000
if vault_cmd sync-receive claude:owner-a < "$CONFLICT" >/dev/null 2>&1; then
    echo "expected conflicting owner sync to fail" >&2
    exit 1
fi
[ "$before" = "$(shasum -a 256 "$canonical")" ]

write_owner_snapshot "$NEWER" newer-access newer-refresh 4102444900000
vault_cmd sync-receive claude:owner-a < "$NEWER"
grep -q newer-refresh "$canonical"

# Concurrent arrivals serialize; the greatest expiry wins regardless of order.
LOW="$VAULT/low.json" HIGH="$VAULT/high.json"
write_owner_snapshot "$LOW" low-access low-refresh 4102445000000
write_owner_snapshot "$HIGH" high-access high-refresh 4102445100000
vault_cmd sync-receive claude:owner-a < "$LOW" >/dev/null 2>&1 & low_pid=$!
vault_cmd sync-receive claude:owner-a < "$HIGH" >/dev/null 2>&1 & high_pid=$!
wait "$low_pid" || true
wait "$high_pid" || true
grep -q high-refresh "$canonical"

# Owner-managed canonical files cannot be refreshed by a later vault publish.
python3 - "$canonical" <<'PY'
import json, sys
p=sys.argv[1]; d=json.load(open(p)); d["claudeAiOauth"]["expiresAt"]=1; json.dump(d,open(p,"w"))
PY
if HOME="$VAULT" CLAUDE_PROFILES_DIR="$VAULT/profiles" CLAUDE_SHARED_DIR="$VAULT/shared" CLAUDE_REAL_BIN="$TMP/bin/claude-real" "$ROOT/claude-token" publish --profile owner-a >"$VAULT/publish-out" 2>"$VAULT/publish-err"; then
    echo "expected owner-managed vault publish to refuse refresh" >&2
    exit 1
fi
grep -q "owner-managed" "$VAULT/publish-err"

# Explicit owner mode refuses publish even for an unmarked local credential.
new_home owner-publish 'mode=owner\n'
mkdir -p "$HOME/.claude-profiles/owner-a/.claude"
write_owner_snapshot "$HOME/.claude-profiles/owner-a/.claude/credentials.json" access refresh 1
if run_token publish --profile owner-a >"$HOME/stdout" 2>"$HOME/stderr"; then
    echo "expected publish to be disabled in owner mode" >&2
    exit 1
fi
grep -q "publish is disabled in owner mode" "$HOME/stderr"

echo "ok: owner safety and follower freshness"
