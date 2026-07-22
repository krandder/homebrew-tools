#!/usr/bin/env bash
# ai-token bootstrap — the ONE line that works from any machine state:
#
#   curl -fsSL https://raw.githubusercontent.com/krandder/homebrew-tools/main/bootstrap.sh | bash
#
# Optional follower onboarding in the same line:
#   ... | bash -s -- --token <T> --user <name> [--tool claude] [--url https://vault.ekelvin.com]
#
# Idempotent by design: safe to re-run; each step is a no-op when already done.
# Handles the three real-world states: fresh machine, legacy raw-script install
# (old ~/.local/bin/*-token files shadowing brew), and existing brew install.
set -euo pipefail

TAP="krandder/tools"
PKG="ai-token"
VAULT_URL="https://vault.ekelvin.com"
TOKEN=""; USER_NAME=""; TOOL="claude"

while [ $# -gt 0 ]; do
    case "$1" in
        --token) TOKEN="$2"; shift 2;;
        --user)  USER_NAME="$2"; shift 2;;
        --tool)  TOOL="$2"; shift 2;;
        --url)   VAULT_URL="$2"; shift 2;;
        *) echo "bootstrap: unknown arg $1" >&2; exit 2;;
    esac
done

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf '  ✗ %s\n' "$*" >&2; exit 1; }

say "ai-token bootstrap"

# 1) brew must exist. Probe standard prefixes too: non-interactive/ssh shells
#    often lack `brew shellenv`, so PATH alone is not enough. Homebrew itself
#    needs an interactive sudo install — the only step we cannot automate.
if ! command -v brew >/dev/null 2>&1; then
    for B in ${BREW_BIN:-} ${BREW_PROBE_PATHS:-/opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew}; do
        [ -n "$B" ] && [ -x "$B" ] && PATH="$(dirname "$B"):$PATH" && break
    done
    hash -r 2>/dev/null || true
fi
if ! command -v brew >/dev/null 2>&1; then
    die "Homebrew not found. Install it first (one line), then re-run this bootstrap:
     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi
ok "brew found: $(command -v brew)"

# 2) ensure the tap (the adriana failure: 'No available formula' == tap missing)
if brew tap | grep -qx "$TAP"; then
    ok "tap $TAP present"
else
    say "  adding tap $TAP"
    brew tap "$TAP" || die "brew tap $TAP failed"
    ok "tap added"
fi

# 3) install or upgrade (never both failing silently again)
brew update >/dev/null 2>&1 || warn "brew update failed (continuing with cached formulae)"
if brew list --versions "$PKG" 2>/dev/null | grep -q .; then
    if OUT=$(brew upgrade "$PKG" 2>&1); then
        ok "$PKG upgraded (or already latest)"
    else
        case "$OUT" in
            *already\ installed*) ok "$PKG already latest";;
            *) printf '%s\n' "$OUT" >&2; die "brew upgrade $PKG failed";;
        esac
    fi
else
    brew install "$PKG" || die "brew install $PKG failed"
    ok "$PKG installed"
fi
brew link --overwrite "$PKG" >/dev/null 2>&1 || true

# 4) de-shadow legacy raw-script copies (the juana/adriana failure: old
#    ~/.local/bin/*-token files winning PATH over the brew shim). We only touch
#    files OUTSIDE the brew prefix, and we rename instead of delete.
BREW_BIN="$(brew --prefix)/bin"
hash -r 2>/dev/null || true
for TOOLNAME in ai-token claude-token codex-token; do
    RESOLVED="$(command -v "$TOOLNAME" 2>/dev/null || true)"
    case "$RESOLVED" in
        ""|"$BREW_BIN"/*) : ;;  # absent, or already the brew one — nothing to do
        *)
            BACKUP="${RESOLVED}.pre-brew-backup"
            mv "$RESOLVED" "$BACKUP" && warn "legacy $TOOLNAME at $RESOLVED shadowed brew; moved to $BACKUP"
            hash -r 2>/dev/null || true
            ;;
    esac
done

# 5) verify the shim chain answers (fall back to brew prefix when the user's
#    PATH hasn't picked it up yet, e.g. fresh shell config)
AI_TOKEN_BIN="$(command -v ai-token || true)"
if [ -z "$AI_TOKEN_BIN" ] && [ -x "$BREW_BIN/ai-token" ]; then
    AI_TOKEN_BIN="$BREW_BIN/ai-token"
    warn "ai-token not on PATH yet — add $BREW_BIN to your shell PATH (new shells usually have it)"
fi
[ -n "$AI_TOKEN_BIN" ] || die "ai-token not found after install"
V="$("$AI_TOKEN_BIN" claude --version 2>/dev/null || true)"
[ -n "$V" ] || die "ai-token installed but 'claude --version' produced nothing"
ok "ready: $V"

# 6) optional follower onboarding
if [ -n "$TOKEN" ] && [ -n "$USER_NAME" ]; then
    say "  pairing follower $USER_NAME with $VAULT_URL"
    "$AI_TOKEN_BIN" "$TOOL" install --token "$TOKEN" --user "$USER_NAME" --url "$VAULT_URL" --mode follower \
        || die "follower install failed"
    ok "follower $USER_NAME paired"
fi

cat <<EOF

Done. Next steps:
  ai-token claude status                    # see profiles + freshness
  ai-token claude pull --profile <name>     # fetch a profile you were granted
  ai-token claude run --profile <name> -- claude
EOF
