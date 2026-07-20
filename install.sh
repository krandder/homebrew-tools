#!/usr/bin/env bash
# Install krandder/tools to a directory already in PATH

REPO_URL="${REPO_URL:-https://raw.githubusercontent.com/krandder/homebrew-tools/main}"

# Check if directory is in PATH
in_path() {
    [[ ":$PATH:" == *":$1:"* ]]
}

# Find a writable directory that's already in PATH.
find_install_dir() {
    local TOOL="${1:-}"

    # Prefer the directory that currently provides this tool. This avoids
    # installing a fixed copy later in PATH while an older copy keeps winning.
    if [[ -n "$TOOL" ]]; then
        local EXISTING
        EXISTING=$(command -v "$TOOL" 2>/dev/null || true)
        if [[ "$EXISTING" == /* ]]; then
            local EXISTING_DIR
            EXISTING_DIR=$(dirname "$EXISTING")
            if [[ -d "$EXISTING_DIR" && -w "$EXISTING_DIR" ]]; then
                echo "$EXISTING_DIR"
                return 0
            fi
        fi
    fi

    # Priority: /opt/homebrew/bin (Apple Silicon), /usr/local/bin (Intel), then home directories
    for DIR in "/opt/homebrew/bin" "/usr/local/bin" "$HOME/bin" "$HOME/.local/bin"; do
        if in_path "$DIR" && mkdir -p "$DIR" 2>/dev/null && [[ -w "$DIR" ]]; then
            echo "$DIR"
            return 0
        fi
    done
    
    # Fallback: find any writable PATH directory
    IFS=':' read -ra PATH_DIRS <<< "$PATH"
    for DIR in "${PATH_DIRS[@]}"; do
        if [[ -d "$DIR" ]] && [[ -w "$DIR" ]]; then
            echo "$DIR"
            return 0
        fi
    done
    
    # Last resort: create ~/bin
    mkdir -p "$HOME/bin" && echo "$HOME/bin"
}

install_tool() {
    local TOOL=$1
    local INSTALL_DIR
    INSTALL_DIR=$(find_install_dir "$TOOL")

    if [[ -z "$INSTALL_DIR" ]]; then
        echo "Error: Could not find a writable directory in PATH for $TOOL" >&2
        return 1
    fi
    
    echo "Installing $TOOL to: $INSTALL_DIR/$TOOL"
    if curl -fsSL "$REPO_URL/$TOOL" -o "$INSTALL_DIR/$TOOL" && chmod +x "$INSTALL_DIR/$TOOL"; then
        echo "  ✓ $TOOL installed"
        hash -r 2>/dev/null || true
        local RESOLVED
        RESOLVED=$(command -v "$TOOL" 2>/dev/null || true)
        echo "  resolved: ${RESOLVED:-not found on PATH}"
        if [[ "$RESOLVED" != "$INSTALL_DIR/$TOOL" ]]; then
            echo "  warning: PATH resolves $TOOL somewhere else; run: type -a $TOOL" >&2
        fi
        return 0
    else
        echo "  ✗ $TOOL installation failed" >&2
        return 1
    fi
}

# Install the canonical implementation before its compatibility entrypoints.
install_tool "ai-token"

# Install claude-token
install_tool "claude-token"

# Install codex-token  
install_tool "codex-token"

echo ""
echo "✓ Installation complete!"
echo ""
echo "Test them now:"
echo "  claude-token"
echo "  codex-token"

# Warn if ~/bin was created and might not be in PATH
if [[ -d "$HOME/bin" ]] && [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
    echo ""
    echo "Note: $INSTALL_DIR may not be in your PATH yet."
    echo "Add this to your shell config (~/.zshrc or ~/.bashrc):"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi
