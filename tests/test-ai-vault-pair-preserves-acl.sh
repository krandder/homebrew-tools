#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/vault"
printf '%s\n' '{"operator":"admin","admins":["admin"],"profiles":{"codex:kas":{"owner":"kas","pullers":["kas","helper"],"kind":"codex"},"claude:kas":{"owner":"kas","pullers":["kas","helper"],"kind":"claude"}}}' > "$TMP/vault/acl.json"

vault() {
    CODEX_VAULT_USER=admin CODEX_VAULT_DIR="$TMP/vault" "$ROOT/ai-vault" "$@"
}

vault pair-create kas PAIR123 hash >/dev/null
vault pair-approve PAIR123 >/dev/null 2>&1

python3 - "$TMP/vault/acl.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for profile in ("codex:kas", "claude:kas"):
    assert d["profiles"][profile]["owner"] == "kas"
    assert d["profiles"][profile]["pullers"] == ["kas", "helper"]
PY

CODEX_VAULT_USER=helper CODEX_VAULT_DIR="$TMP/vault" "$ROOT/ai-vault" authorize-pull claude:kas
if CODEX_VAULT_USER=stranger CODEX_VAULT_DIR="$TMP/vault" "$ROOT/ai-vault" authorize-pull claude:kas 2>/dev/null; then
    echo "expected unrelated identity to be denied" >&2
    exit 1
fi

echo "ok: repeated pairing preserves existing ACLs and pull authorization"
