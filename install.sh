#!/usr/bin/env bash
# Install krandder/tools to a directory already in PATH

REPO_URL="https://raw.githubusercontent.com/krandder/homebrew-tools/main"

# Check if directory is in PATH
in_path() {
    [[ ":$PATH:" == *":$1:"* ]]
}

# Find a writable directory that's already in PATH
find_install_dir() {
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
    local INSTALL_DIR=$2
    
    echo "Installing $TOOL to: $INSTALL_DIR/$TOOL"
    if curl -fsSL "$REPO_URL/$TOOL" -o "$INSTALL_DIR/$TOOL" && chmod +x "$INSTALL_DIR/$TOOL"; then
        echo "  ✓ $TOOL installed"
        return 0
    else
        echo "  ✗ $TOOL installation failed" >&2
        return 1
    fi
}

# Main
INSTALL_DIR=$(find_install_dir)

if [[ -z "$INSTALL_DIR" ]]; then
    echo "Error: Could not find a writable directory in PATH" >&2
    exit 1
fi

echo "Installing to: $INSTALL_DIR"
echo ""

# Install claude-token
install_tool "claude-token" "$INSTALL_DIR"

# Install codex-token  
install_tool "codex-token" "$INSTALL_DIR"

echo ""
echo "✓ Installation complete!"
echo ""
echo "Test them now:"
echo "  claude-token"
echo "  codex-token"

# Warn if ~/bin was created and might not be in PATH
if [[ "$INSTALL_DIR" == "$HOME/bin" ]] && [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
    echo ""
    echo "Note: $INSTALL_DIR may not be in your PATH yet."
    echo "Add this to your shell config (~/.zshrc or ~/.bashrc):"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi
