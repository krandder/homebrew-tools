# Token Vault — Work Summary, Challenges & Next Steps

Narrative retro of the effort to share Codex/Claude accounts across machines
without their refresh tokens invalidating each other. Companion to `VAULT.md`
(architecture/state). Last updated: 2026-07-02.

## Goal
Several people/machines needed to use the same OpenAI Codex (and Anthropic
Claude) accounts. Doing it naively broke constantly: both providers use
**rotating, single-owner refresh tokens**, so two machines holding a refresh
token for one account invalidate each other on refresh (`refresh_token_reused`).

## What we built (work so far)
1. **Discovery (the foundation):** confirmed the invalidation model; learned
   access tokens are bearer + ~10-day-lived (`expires_in=864000`); that Codex
   *requires* a refresh token present to even send the bearer and refreshes
   internally; that `CODEX_REFRESH_TOKEN_URL_OVERRIDE` can blackhole refresh;
   and that Claude honors `ANTHROPIC_AUTH_TOKEN` env over Keychain.
2. **Leader/follower model:** one leader owns each account's real refresh token;
   followers run with a *sentinel* refresh token + blackholed refresh (Codex) or
   an env-injected access token (Claude) — so they **cannot rotate** the leader's token.
3. **Tools (in this tap):** `codex-token` (client, 2.6.0), `codex-vault` (leader,
   1.3.0), `codex-vault-http` (HTTPS front-end, 1.1.0), plus `claude-token`
   (2.0.0) and the operator-only `ai-as` launcher (not in tap).
4. **Public vault at `vault.ekelvin.com`:** Cloudflare Tunnel → `codex-vault-http`
   on farol. Bearer API tokens, ACL (owner-push / puller-pull), audit log.
5. **Magical onboarding:** `codex-token install` (user defaults to computer name)
   emits a short pairing code → operator `codex-vault pair-approve <code>` →
   follower auto-completes (enroll + token + pull + wrappers). No token copy-paste.
6. **Claude parity:** `claude-<user>` launchers, `claude login` auto-pushes,
   `claude-run --user`. `claude-owner-a` now works on the mac (shares `~/.claude`
   conversations with the default login; only the auth account differs).
7. **Keep-fresh cron** on farol (`codex-token publish --all` + `claude-token publish --all`, every 6h).

## Challenges & how we solved them
- **Mutual refresh-token invalidation** → single leader + sentinel/blackhole (Codex)
  and env access-token (Claude); real refresh tokens never leave the leader.
- **Codex refuses to send the bearer without a refresh token** → followers carry a
  *sentinel* (dummy) refresh token so creds look complete, plus the blackhole so
  it never actually refreshes.
- **`push` used the local `$HOME` path on the leader** → fixed to use the leader's `$HOME`.
- **Two-step `set-url`/`set-token` UX** → folded into one `install`; URL defaults to `https://vault.ekelvin.com`.
- **Cloudflare tunnel is remote-managed** (local `config.yml` ignored) → added the
  `vault.ekelvin.com` ingress via the Cloudflare API, preserving all existing routes.
- **No obvious Cloudflare API token on farol** → found the global API key in
  `secrets.env`; created the `vault` CNAME via the API.
- **Pairing token got contaminated** (`say` wrote to stdout, captured into the
  token) → moved status to stderr so only the token is captured.
- **New (non-admin) user failed `/status` verify** → switched to the user's own
  `/pull/<kind>/<user>` (anything but 401).
- **GitHub `raw.githubusercontent` cache lag** repeatedly stalled `brew upgrade`
  → pinned the `codex-token` formula URL to the commit SHA (instant, deterministic).
- **Claude refresh rate-limited** (transient) → manually published the existing
  access token to unblock, plus added the claude publish cron to keep it fresh.
- **Conversation isolation** (`CLAUDE_CONFIG_DIR` per user) → implemented, then
  **reverted** — sharing `~/.claude` across accounts was the desired behavior.

## Current state
- **farol (leader):** Codex `operator`/`owner-a`/`owner-c` live; `stale-a`/`stale-b` dead
  (need relogin). Claude `owner-a` revived (working); `operator` enrolled. ACL admin = `operator`.
- **mac (follower/operator):** Codex via Syncthing mesh (`operator`/`owner-a`/`owner-c`,
  sentinel RT). `claude-owner-a` working (shared `~/.claude`). `codex-token` 2.6.0.
- **`vault.ekelvin.com`** live (healthz, `/status`, `/pull`, `/push`, `/pair`).
- Tap on GitHub `main`; codex-token formula pinned to commit SHA.

## Next possible steps
- **Adopt commit-SHA URL pinning** for the other formulae (`codex-vault`,
  `codex-vault-http`, `claude-token`) — kills the raw-cache lag everywhere.
- **Revive dead accounts:** relogin Codex `stale-a`/`stale-b` (and any stale Claude)
  via `codex-<p> login` / `claude-login --user <u>` → push to vault.
- **Token revocation:** `codex-vault revoke-token <user>` + `list-tokens` (today
  tokens can only be removed by editing `tokens.json`).
- **Encryption-at-rest** for the leader's refresh tokens (age / OS keyring).
- **Refresh `codex-vault --help`** (stale — doesn't list `token`/`approve`/`onboard`/`pair-*`).
- **mac Claude follower for `operator`** (so the operator can run `claude-operator` too).
- **farol reachability:** fix the stale direct IP or standardize on Tailscale/`vault.ekelvin.com`.
- **Optional:** unified `codex-vault auths` / `/auths` status; richer pairing
  (pubkey-encrypted token delivery); per-account claude data dir as an *opt-in* flag.

## Key locations
- Client config: `~/.codex-token/config` (`user`, `token`, `url`)
- Vault state (leader): `~/.codex-vault/{acl.json, tokens.json, audit.jsonl, pairings.json}`
- Canonical auth (leader): `~/.codex-profiles/<n>/.codex/auth.json`,
  `~/.claude-profiles/<n>/.claude/credentials.json`
- Published follower tokens: `~/shared/{codex,claude}-tokens/<name>.json`
- Public endpoint: `https://vault.ekelvin.com` (Cloudflare tunnel `8e5ae8e1-…`)
