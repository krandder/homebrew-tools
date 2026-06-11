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

Outputs Claude's native OAuth JSON with `accessToken`, `refreshToken`, `expiresAt`, `scopes`, `subscriptionType`, etc.

Works on macOS and Linux. Automatically detects:
- macOS Keychain (`Claude Code-credentials`)
- `~/.claude/.credentials.json` file
- `~/.claude/credentials.json` file
- `CLAUDE_CODE_OAUTH_TOKEN` environment variable as a last-resort access-token-only fallback

`CLAUDE_CODE_OAUTH_TOKEN` is usually only an `sk-ant-oat...` access token and does not contain the `sk-ant-ort...` refresh token. `claude-token` therefore prefers Keychain / credentials files when available.

If no refresh token is found, `claude-token` prints diagnostics to stderr showing which credential sources were checked, whether JSON parsed, and whether `accessToken` / `refreshToken` fields were present. Token values are not printed in diagnostics.

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
