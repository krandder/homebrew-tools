#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
cat > "$TMP/bin/brew" <<'SH'
#!/usr/bin/env bash
printf 'brew %s\n' "$*" >> "$CALLS"
exit 0
SH
cat > "$TMP/bin/claude-token" <<'SH'
#!/usr/bin/env bash
printf 'claude-token %s\n' "$*" >> "$CALLS"
SH
chmod +x "$TMP/bin/"*
CALLS="$TMP/calls" PATH="$TMP/bin:/usr/bin:/bin" "$ROOT/setup-claude-token" owner-a
printf '%s\n' 'brew update' 'brew list --versions krandder/tools/claude-token' \
  'brew upgrade krandder/tools/claude-token' 'claude-token setup-owner owner-a' > "$TMP/expected"
cmp "$TMP/expected" "$TMP/calls"
echo "ok: bootstrap upgrades and continues into owner setup"
