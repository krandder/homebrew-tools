# homebrew-tools

Personal Homebrew tap for useful CLI tools.

## Available Formulae

### `claude-token`

Print and **sync Claude Code OAuth credentials across machines** using the same
owner/follower vault as `codex-token`. Works for Claude Code's OAuth on
`platform.claude.com` (access tokens `sk-ant-oat…`, refresh tokens `sk-ant-ort…`).

**Install:**
```bash
brew tap krandder/tools
brew install claude-token
```

#### How it works
- An **owner machine** keeps its normal Claude login and remains the sole
  refresh authority. Plain `claude`, browser login, and native refresh do not
  depend on the vault. A real local refresh token always wins over configured
  follower mode until an explicit legacy handoff demotes it.
- `claude-token sync` copies a fresh owner snapshot to Farol without modifying
  local credentials. Farol rejects stale/conflicting snapshots and never
  refreshes owner-managed Claude credentials.
- **Followers** run with a *sentinel* refresh token. Claude Code uses the fresh
  access bearer directly and **cannot rotate** the owner's token. Every launch
  validates `expiresAt`; stale local and vault tokens are rejected.
- Creds are stored in the macOS **Keychain** (`Claude Code-credentials`) on
  Darwin and `~/.claude/.credentials.json` on Linux.

#### Commands (mirror `codex-token`)
```
claude-token                              print active account tokens (default)
claude-token check                        validate creds without printing secrets
claude-token status / set-url / set-token / set-mode
claude-token pair --user NAME             protective auto mode; preserves a local owner login
claude-token pair --user NAME --owner     owner mode; leaves plain claude untouched
claude-token pair --user NAME --follower  explicit follower mode; installs wrapper
claude-token login                        native browser OAuth + best-effort sync
claude-token sync [--profile P]           copy credentials; never changes local Claude
claude-token run [claude args...]         follower launcher (freshen store, exec claude)
claude-token publish [--profile P|--all]  LEADER: refresh + publish follower token
claude-token pull [--profile P]           FOLLOWER: replace local store with follower token
claude-token push [--profile P]           LEGACY HANDOFF: sync, then demote local credentials
claude-token check | --diagnose | --version
```

Owner-machine onboarding (Adriana/Juana):
```bash
claude-token pair --user NAME --owner
claude-token login
# Plain claude remains native. Re-run this safely whenever needed:
claude-token sync --profile NAME
```

Pairing/onboarding is identical to `codex-token` (pair → operator `ai-vault
approve`/`enroll … claude` + `token` → `set-url`/`set-token` → `login`). Profile
ids in the vault are composite `<kind>:<name>` (e.g. `claude:kas`, `codex:kas`),
so the same name can exist for both tools.

---

### `claude-token` (legacy extract-only)

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

For explicit diagnostics or version checks:

```bash
claude-token --diagnose
claude-token check
claude-token --version
```

---

### `codex-token`

Print and **sync OpenAI Codex CLI credentials across machines** using a leader/follower model, so several people/machines can share Codex accounts without their refresh tokens invalidating one another.

**Install:**
```bash
brew tap krandder/tools
brew install codex-token
```

#### How it works
- Exactly **one leader** machine owns each account's real refresh token and refreshes it (access tokens live ~10 days).
- **Followers** run with a *sentinel* refresh token and the refresh endpoint overridden to a blackhole (`CODEX_REFRESH_TOKEN_URL_OVERRIDE`), so they use the leader's fresh access token but can **never rotate** it.
- The leader publishes fresh access tokens to a Syncthing-shared folder (`~/shared/codex-tokens/`); followers pull from there (fast path) or from the vault (ACL-gated).

#### Commands
```
codex-token                                 print active account tokens (default; backward compatible)
codex-token status [--profile P|--all]      roles, token age, sync health (no secrets)
codex-token pair --user NAME                generate a vault key + print the line to send the operator
codex-token login                           browser OAuth → push to leader → become a follower
codex-token run [codex args...]             follower launcher: freshen ~/.codex, then exec codex (refresh blackholed)
codex-token install-wrapper                 make plain `codex` run via `codex-token run`
codex-token publish [--profile P|--all]     LEADER: refresh + publish a token to the shared folder
codex-token pull [--profile P|--all]        FOLLOWER: pull a published token into a local profile
codex-token push [--profile P]              push a local real token to the leader (owner-gated)
codex-token sync [--profile P|--all]        role-aware one-shot (publish/push/pull)
codex-token --diagnose | --version | --help
```

#### New user onboarding (e.g. "fred", fresh machine, homebrew only)
```bash
brew tap krandder/tools && brew install codex-token
codex-token pair --user fred        # prints one command=... line — send it to the operator
# …operator runs, on the leader:  ai-vault approve fred '<that line>'
codex-token login                   # browser sign-in as fred's account → pushes to leader
codex-token install-wrapper         # plain `codex` now runs as fred's follower account
codex                               # works
```

#### Operator (multi-account on one machine)
Install `codex-token` plus the `ai-as` launcher (not in this tap) for `codex-<profile>` switching. Each profile dir is `~/.codex-profiles/<name>/.codex/`; role is stored in `~/.codex-profiles/<name>/.role`.

Environment: `CODEX_USER`, `CODEX_PROFILE`, `CODEX_LEADER` (default `farol-ts`), `CODEX_PROFILES_DIR`, `CODEX_SHARED_DIR`, `CODEX_VAULT_KEY`.

---

### `ai-vault`

Leader-side **token vault with per-user ACL and audit**. Runs on the leader (e.g. `farol`). Holds the canonical refresh tokens, enforces who may **push** (the profile owner) and **pull** (granted pullers/admins), refreshes + publishes follower tokens, and keeps an append-only audit log. Identity is bound to each user's SSH key via an SSH forced command (`ai-vault shell <user>`).

**Install (on the leader):**
```bash
brew tap krandder/tools && brew install ai-vault   # depends on codex-token
```

#### Commands
```
ai-vault approve USER '<pubkey-line>'    enroll USER + install their key with a forced command (admin)
ai-vault enroll USER OWNER               register a profile (admin)
ai-vault grant  PROFILE USER             allow USER to pull PROFILE (admin/owner)
ai-vault revoke PROFILE USER             remove USER's pull right (admin/owner)
ai-vault receive PROFILE                 read a token on stdin, store + refresh + publish (owner)
ai-vault serve  PROFILE                  write the follower token to stdout (puller)
ai-vault list                            show the ACL (admin)
ai-vault show-audit [N]                  last N audit entries (admin)
ai-vault whoami                          print identity + admin flag
ai-vault shell USER -- <cmd>             SSH forced-command wrapper (binds identity to USER)
```

The ACL lives at `~/.ai-vault/acl.json` (`{admins, operator, profiles:{NAME:{owner,pullers}}}`); audit at `~/.ai-vault/audit.jsonl`.

---

## Quick Install (No Homebrew)

```bash
# Claude token
curl -fsSL https://raw.githubusercontent.com/krandder/homebrew-tools/main/install.sh | bash

# Or install both
brew tap krandder/tools
brew install claude-token codex-token
```
