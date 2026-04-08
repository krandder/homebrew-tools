#!/usr/bin/env bash
# Install claude-token to the first available directory in PATH

SCRIPT_URL="https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-token"

# Find a writable directory in PATH
for DIR in "$HOME/bin" "$HOME/.local/bin" "/usr/local/bin" "/opt/homebrew/bin"; do
    if mkdir -p "$DIR" 2>/dev/null && [[ -w "$DIR" ]]; then
        INSTALL_DIR="$DIR"
        break
    fi
done

if [[ -z "$INSTALL_DIR" ]]; then
    echo "Error: Could not find a writable directory in PATH" >&2
    exit 1
fi

# Download and install
curl -fsSL "$SCRIPT_URL" -o "$INSTALL_DIR/claude-token" && chmod +x "$INSTALL_DIR/claude-token"

if [[ $? -eq 0 ]]; then
    echo "✓ Installed to: $INSTALL_DIR/claude-token"
    
    # Add to PATH if needed (for ~/bin or ~/.local/bin)
    if [[ "$INSTALL_DIR" == "$HOME"* ]]; then
        if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
            SHELL_RC="$HOME/.$(basename "$SHELL")rc"
            echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$SHELL_RC"
            echo "✓ Added $INSTALL_DIR to PATH in $SHELL_RC"
            echo "  Run 'source $SHELL_RC' or restart Terminal to use claude-token"
        fi
    fi
else
    echo "Error: Installation failed" >&2
    exit 1
fi
