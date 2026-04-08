# homebrew-tools

Personal Homebrew tap for useful CLI tools.

## Available Formulae

### `claude-token`

Extracts Claude Code authentication token from macOS Keychain or credentials file.

**Install:**
```bash
brew tap krandder/tools
brew install claude-token
```

**Usage:**
```bash
claude-token
```

Works on macOS and Linux. Automatically detects:
- `CLAUDE_CODE_OAUTH_TOKEN` environment variable
- macOS Keychain (`Claude Code-credentials`)
- `~/.claude/.credentials.json` file
