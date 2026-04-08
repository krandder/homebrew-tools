#!/usr/bin/env bash
# Install claude-token to a directory already in PATH

SCRIPT_URL="https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"

# Check if directory is in PATH
in_path() {
    [[ ":$PATH:" == *":$1:"* ]]
}

# Find a writable directory that's already in PATH
# Priority: /opt/homebrew/bin (Apple Silicon), /usr/local/bin (Intel), then home directories
for DIR in "/opt/homebrew/bin" "/usr/local/bin" "$HOME/bin" "$HOME/.local/bin"; do
    if in_path "$DIR" && mkdir -p "$DIR" 2>/dev/null && [[ -w "$DIR" ]]; then
        INSTALL_DIR="$DIR"
        break
    fi
done

# Fallback: find any writable PATH directory
if [[ -z "$INSTALL_DIR" ]]; then
    IFS=':' read -ra PATH_DIRS <<< "$PATH"
    for DIR in "${PATH_DIRS[@]}"; do
        if [[ -d "$DIR" ]] && [[ -w "$DIR" ]]; then
            INSTALL_DIR="$DIR"
            break
        fi
    done
fi

# Last resort: create ~/bin and add to PATH
if [[ -z "$INSTALL_DIR" ]]; then
    INSTALL_DIR="$HOME/bin"
    mkdir -p "$INSTALL_DIR"
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> ~/.zshrc
    echo "Note: Added $INSTALL_DIR to PATH in ~/.zshrc"
    echo "Run 'source ~/.zshrc' or restart Terminal after install"
fi

# Download and install
echo "Installing to: $INSTALL_DIR/claude-token"
if curl -fsSL "$SCRIPT_URL" -o "$INSTALL_DIR/claude-token" && chmod +x "$INSTALL_DIR/claude-token"; then
    echo "✓ Installed successfully!"
    echo ""
    echo "Test it now:"
    echo "  claude-token"
else
    echo "Error: Installation failed" >&2
    exit 1
fi
