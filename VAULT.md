# Codex / Claude Token Vault — Status & Architecture

Living doc for the leader/follower credential-sharing system built on top of the
`krandder/homebrew-tools` tap. Last updated: 2026-07-02.

## The problem we solved
OpenAI Codex (and Anthropic Claude) use **rotating, single-owner refresh tokens**:
two machines both holding a refresh token for the same account invalidate each
other on refresh ("refresh token was already used"). This made sharing one
account across several machines/people impossible without constant re-logins.

## The model
- **One leader** owns each account's real refresh token and refreshes it.
- **Followers** never hold a real refresh token:
  - **Codex followers** run with a *sentinel* refresh token + the refresh
    endpoint overridden to a blackhole (`CODEX_REFRESH_TOKEN_URL_OVERRIDE`), so
    they use the leader's fresh access token but **cannot rotate** it.
  - **Claude followers** inject the leader's access token via `ANTHROPIC_AUTH_TOKEN`
    (Claude honors env auth over Keychain).
- Access tokens are bearer tokens, valid ~10 days (Codex `expires_in=864000`),
  and are what followers actually use. The real refresh token never leaves the leader.
- The leader publishes fresh access tokens to a Syncthing-shared folder
  (`~/shared/codex-tokens`, `~/shared/claude-tokens`); followers pull from there
  (fast path) or from the HTTPS vault (ACL-gated).

## Components (in this tap)
| tool | role | where |
|---|---|---|
| `codex-token` (2.3.0) | **client** — print/sync, `install`, `login`, `run`, `claude-run`, pairing | every machine |
| `codex-vault` (1.3.0) | **leader** — ACL, audit, `receive`/`serve`, `onboard`, `pair-approve`, `token` | farol |
| `codex-vault-http` (1.1.0) | **HTTPS front-end** — bearer auth, `/pair`, `/pull`, `/push`, `/status` | farol (behind tunnel) |
| `claude-token` (2.0.0) | claude creds extractor + `publish`/`pull`/`push` | farol + clients |
| `ai-as` (not in tap) | operator-only multi-account launcher (`codex-<profile>`/`claude-<profile>`) | operator machines |

Profiles are tool-aware and composite: `<kind>:<name>` (e.g. `codex:operator`, `claude:owner-a`).

## Infrastructure (deployed)
- **Leader:** `farol` (Debian, always-on). `codex-vault-http` runs as a rootless
  systemd service on `127.0.0.1:8231`. A cron runs `codex-token publish --all`
  every ~6h to keep Codex follower tokens fresh.
- **Public endpoint:** `https://vault.ekelvin.com` → Cloudflare Tunnel
  (`8e5ae8e1-…`) → `127.0.0.1:8231`. The tunnel is **remote-managed**, so its
  ingress lives in Cloudflare (not the local `config.yml`). DNS CNAME
  `vault.ekelvin.com` → `<tunnel>.cfargotunnel.com`, created via the Cloudflare
  global API key found in farol's `secrets.env` (zone `ekelvin.com`).
- **Mesh:** Syncthing `~/shared` folder between farol ↔ mac distributes
  published follower tokens read-only (fast pull path for trusted machines).
- **Identity:** HTTPS = per-user API token (sha256-hashed in `~/.codex-vault/tokens.json`).
  SSH path = per-user key with a forced command (`codex-vault shell <user>`).

## Onboarding flows (all working)
- **Magical pairing (preferred):**
  - new machine: `codex-token install` (user defaults to computer name; or `--user fred`)
    → prints a 5-char code → waits.
  - leader: `codex-vault pair-approve <code>` → enrolls `codex:<user>`+`claude:<user>`,
    issues token → follower auto-completes (auth + pull + wrappers).
- **Direct (token):** leader `codex-vault onboard <user>` (prints token) →
  machine `codex-token install --token <t> --user <user>`.
- **SSH:** `codex-token pair` → leader `codex-vault approve <user> '<pubkey-line>'`.

## Current state / inventory
- **farol (leader):**
  - Codex: `operator`, `owner-a`, `owner-c` live (real RT, published); `stale-a`, `stale-b` **dead** (`refresh_token_reused`).
  - Claude: `operator`, `owner-a` enrolled; **owner-a's refresh token is dead** (`claude-token publish` → refresh failed), so no Claude follower token is published.
  - ACL admin/operator = `operator`.
- **mac (follower/operator):**
  - Codex via Syncthing mesh: `operator`, `owner-a`, `owner-c` healthy (sentinel RT, ~9d tokens). `codex`/`codex-operator`/`codex-owner-a`/`codex-owner-c` launchers work.
  - Claude: **not configured** (no `claude-<user>` launcher, no `~/.codex-token/config`, single Keychain account = `user@example.com`).
- **Tap:** pushed to GitHub `main` (codex-token 2.3.0 / codex-vault 1.3.0 / codex-vault-http 1.1.0).

## Blockers / unresolved
1. **Dead refresh tokens** — Codex `stale-a`/`stale-b`, Claude `owner-a` (and any
   other stale Claude logins). *Unblocker:* a fresh `codex login` / `claude login`
   as that user on any machine, then push to the vault. Cannot be automated
   around a revoked token.
2. **Claude client-side is incomplete:**
   - No `claude-<user>` launcher; `claude-run` has no `--user`.
   - `claude login` does **not** auto-push to the vault (unlike `codex login`).
   - mac has no Claude follower config / no mesh pull for `claude-tokens`.
3. **No Claude publish cron** on farol (only Codex is kept fresh automatically).
4. **No token revocation** — issued API tokens can't be invalidated except by
   editing `tokens.json` by hand.
5. **farol direct IP stale** (`179.111.200.44:2342`) — everything uses `farol-ts`
   (Tailscale) or `vault.ekelvin.com`.
6. **No encryption-at-rest** for the canonical refresh tokens on farol (files are 0600 only).
7. **Stale help text** in `codex-vault --help` (doesn't list `token`/`approve`/`onboard`/`pair-*`).
8. **GitHub `raw.githubusercontent` cache lag** can make `brew upgrade` briefly
   fail the SHA check right after a push (self-heals in a few minutes).

## Likely next steps
- **Revive dead accounts:** relogin Codex `stale-a`/`stale-b` and Claude `owner-a`,
  push to vault.
- **Finish Claude client parity:** add `claude-run --user`, `claude-<user>`
  symlinks, and wire `claude login` → push (so Claude onboarding matches Codex).
- **Add a Claude publish cron** on farol (`claude-token publish --all`).
- **Token lifecycle:** `codex-vault revoke-token <user>` + `list-tokens`.
- **Encryption-at-rest** for refresh tokens (age / OS keyring).
- **Standardize farol reachability:** fix dynamic DNS or commit to Tailscale/`vault.ekelvin.com`.
- **Refresh `codex-vault --help`** to document the full command set.
- *Optional:* mac Claude follower setup (so the operator can run `claude-operator`);
  a `codex-vault auths`/`/auths` unified status; pin formula URLs to commit SHAs
  to avoid the raw-cache lag.

## Key locations
- Config (client): `~/.codex-token/config` (`user=`, `token=`, `url=`)
- Vault state (leader): `~/.codex-vault/{acl.json, tokens.json, audit.jsonl, pairings.json}`
- Canonical auth (leader): `~/.codex-profiles/<name>/.codex/auth.json`,
  `~/.claude-profiles/<name>/.claude/credentials.json`
- Published follower tokens: `~/shared/{codex,claude}-tokens/<name>.json`
- Tunnel config: Cloudflare dashboard / API (tunnel `8e5ae8e1-42db-4dbd-86e7-cefb1f78251f`,
  account `878924eda0607cab3b6c0c86a9babb3f`)
