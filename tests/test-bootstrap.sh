#!/usr/bin/env bash
# test-bootstrap.sh — offline tests for bootstrap.sh using a mocked brew.
# Scenarios: fresh machine, legacy-shadowed machine, idempotent re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOOTSTRAP="$ROOT/bootstrap.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
check() { # check <name> <condition...>
    local name="$1"; shift
    if "$@" >/dev/null 2>&1; then PASS=$((PASS+1)); echo "ok   $name";
    else FAIL=$((FAIL+1)); echo "FAIL $name"; fi
}

# --- mock brew factory ------------------------------------------------------
# make_brew <dir> <state>   state: fresh | tapped | installed
make_brew() {
    local dir="$1" state="$2"
    mkdir -p "$dir/prefix/bin"
    cat > "$dir/brew" <<'MOCK'
#!/usr/bin/env bash
# mock brew: logs calls, simulates tap/install/upgrade/link/--prefix
STATE_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "brew $*" >> "$STATE_DIR/calls.log"
case "$1" in
    tap)
        if [ $# -eq 1 ]; then
            [ -f "$STATE_DIR/tapped" ] && echo "krandder/tools" || true
        else
            touch "$STATE_DIR/tapped"
        fi;;
    update) : ;;
    list)
        if [ "$2" = "--versions" ] && [ -f "$STATE_DIR/installed" ]; then
            echo "ai-token 3.0.1"
        else
            echo "Error: No such keg: $STATE_DIR/prefix/Cellar/ai-token" >&2; exit 1
        fi;;
    install)
        touch "$STATE_DIR/installed"
        cat > "$STATE_DIR/prefix/bin/ai-token" <<'SH'
#!/usr/bin/env bash
[ "$1 $2" = "claude --version" ] && echo "claude-token 3.0.1" || echo "ai-token mock"
SH
        chmod +x "$STATE_DIR/prefix/bin/ai-token";;
    upgrade)
        [ -f "$STATE_DIR/installed" ] || { echo "Error: ai-token not installed" >&2; exit 1; }
        echo "ai-token 3.0.1 already installed";;
    link) : ;;
    --prefix) echo "$STATE_DIR/prefix";;
    *) echo "mock brew: unhandled $*" >&2; exit 1;;
esac
MOCK
    chmod +x "$dir/brew"
    if [ "$state" = "tapped" ]; then touch "$dir/tapped"; fi
    if [ "$state" = "installed" ]; then
        touch "$dir/installed" "$dir/tapped"
        "$dir/brew" install >/dev/null 2>&1 || true
        rm -f "$dir/calls.log"
    fi
}

run_bootstrap() { # run_bootstrap <state-dir> [args...]   (never dies under set -e)
    local dir="$1"; shift
    if PATH="$dir/prefix/bin:$dir:$PATH" bash "$BOOTSTRAP" "$@" > "$dir/out.log" 2>&1; then
        return 0
    else
        echo "run_bootstrap FAILED ($dir):" >&2; cat "$dir/out.log" >&2; return 1
    fi
}

# --- scenario 1: fresh machine ----------------------------------------------
S1="$TMP/s1"; mkdir -p "$S1"; make_brew "$S1" fresh
run_bootstrap "$S1"
check "s1: bootstrap exits 0 on fresh machine" true
check "s1: tap was added" grep -q "brew tap krandder/tools" "$S1/calls.log"
check "s1: install was called" grep -q "brew install ai-token" "$S1/calls.log"
check "s1: reports ready" grep -q "ready: claude-token 3.0.1" "$S1/out.log"

# --- scenario 2: legacy shadowed machine ------------------------------------
S2="$TMP/s2"; mkdir -p "$S2/.local/bin"; make_brew "$S2" installed
# legacy raw-script install shadowing the brew shim
printf '#!/bin/sh\necho claude-token 2.4.4\n' > "$S2/.local/bin/claude-token"
chmod +x "$S2/.local/bin/claude-token"
PATH="$S2/.local/bin:$S2:$PATH" bash "$BOOTSTRAP" > "$S2/out.log" 2>&1
check "s2: bootstrap exits 0 with legacy shadow" true
check "s2: upgrade (not install) path" grep -q "brew upgrade ai-token" "$S2/calls.log"
check "s2: legacy file moved to backup" test -f "$S2/.local/bin/claude-token.pre-brew-backup"
check "s2: shadow gone from PATH dir" test ! -e "$S2/.local/bin/claude-token"
check "s2: warning printed" grep -q "shadowed brew" "$S2/out.log"

# --- scenario 3: idempotent re-run ------------------------------------------
run_bootstrap "$S1"
check "s3: second run exits 0" true
check "s3: no duplicate tap" bash -c "[ \$(grep -c 'brew tap krandder/tools' '$S1/calls.log') -eq 1 ]"
check "s3: second run upgrades, not installs" bash -c "[ \$(grep -c 'brew install ai-token' '$S1/calls.log') -eq 1 ]"

# --- scenario 4: no brew → clear error, nonzero ------------------------------
S4="$TMP/s4"; mkdir -p "$S4"
if PATH="$S4:/usr/bin:/bin" bash "$BOOTSTRAP" > "$S4/out.log" 2>&1; then
    echo "FAIL s4: should fail without brew"; FAIL=$((FAIL+1))
else
    PASS=$((PASS+1)); echo "ok   s4: fails cleanly without brew"
fi
check "s4: prints homebrew install hint" grep -q "Homebrew not found" "$S4/out.log"

# --- scenario 5: brew off PATH (ssh/non-login shell) via BREW_BIN ------------
S5="$TMP/s5"; mkdir -p "$S5"; make_brew "$S5" installed
PATH="/usr/bin:/bin" BREW_BIN="$S5/brew" bash "$BOOTSTRAP" > "$S5/out.log" 2>&1
check "s5: works with brew off PATH via BREW_BIN" grep -q "ready: claude-token 3.0.1" "$S5/out.log"

echo
echo "bootstrap tests: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
