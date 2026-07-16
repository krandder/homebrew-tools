#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/vault"
printf '%s\n' '{"operator":"admin","admins":["admin"],"profiles":{"codex:operator":{"owner":"operator","pullers":["operator","helper"],"kind":"codex"},"claude:operator":{"owner":"operator","pullers":["operator","helper"],"kind":"claude"}}}' > "$TMP/vault/acl.json"

vault() {
    CODEX_VAULT_USER=admin CODEX_VAULT_DIR="$TMP/vault" "$ROOT/ai-vault" "$@"
}

vault pair-create operator PAIR123 hash >/dev/null
vault pair-approve PAIR123 >/dev/null 2>&1

python3 - "$TMP/vault/acl.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for profile in ("codex:operator", "claude:operator"):
    assert d["profiles"][profile]["owner"] == "operator"
    assert d["profiles"][profile]["pullers"] == ["operator", "helper"]
PY

CODEX_VAULT_USER=helper CODEX_VAULT_DIR="$TMP/vault" "$ROOT/ai-vault" authorize-pull claude:operator
if CODEX_VAULT_USER=stranger CODEX_VAULT_DIR="$TMP/vault" "$ROOT/ai-vault" authorize-pull claude:operator 2>/dev/null; then
    echo "expected unrelated identity to be denied" >&2
    exit 1
fi

echo "ok: repeated pairing preserves existing ACLs and pull authorization"
