# homebrew-tools

Personal Homebrew tap for useful CLI tools.

## Available Formulae

### `claude-token`

Extracts Claude Code authentication credentials from macOS Keychain or credentials file.

**Install:**
```bash
brew tap krandder/tools
brew install claude-token
```

**Usage:**
```bash
claude-token
```

Outputs full OAuth JSON with `access_token`, `refresh_token`, `expiresAt`, `scopes`, `subscriptionType`, etc.

Works on macOS and Linux. Automatically detects:
- `CLAUDE_CODE_OAUTH_TOKEN` environment variable
- macOS Keychain (`Claude Code-credentials`)
- `~/.claude/.credentials.json` file

---

### `codex-token`

Extracts OpenAI Codex CLI authentication credentials.

**Install:**
```bash
brew tap krandder/tools
brew install codex-token
```

**Usage:**
```bash
codex-token
```

Outputs tokens JSON with `access_token`, `refresh_token`, `account_id`, etc.

Automatically detects:
- `OPENAI_API_KEY` environment variable
- `~/.codex/auth.json` file

---

## Quick Install (No Homebrew)

```bash
# Claude token
curl -fsSL https://raw.githubusercontent.com/krandder/homebrew-tools/main/install.sh | bash

# Or install both
brew tap krandder/tools
brew install claude-token codex-token
```
