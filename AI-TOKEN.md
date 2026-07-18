# ai-token — one credential-sync tool for AI CLIs

`ai-token` replaces the forked `claude-token` / `codex-token` scripts with a
single generic tool. Each CLI is a backend section in one file; orchestration
(pair/publish/pull/push/sync/run/maintain) and the vault protocol are shared.

```
ai-token <claude|codex|kimi> <command> [args]
```

The old entrypoints are shims: `claude-token` → `ai-token claude`,
`codex-token` → `ai-token codex` (argv0 basename dispatch; the Homebrew
formula installs symlinks, farol uses self-locating exec shims).

## Backend registry

| | claude | codex | kimi |
|---|---|---|---|
| store | Keychain / `~/.claude/.credentials.json`; canonical `~/.claude-profiles/<p>/.claude/credentials.json` | `~/.codex/auth.json`; canonical `~/.codex-profiles/<p>/.codex/auth.json` + `.role` | `~/.kimi-code/credentials/kimi-code.json`; canonical `~/.kimi-profiles/<p>/credentials.json` |
| shape | flat camelCase, `expiresAt` ms | nested `tokens{}`, expiry = JWT `exp` | flat snake_case, `expires_at` **seconds**, `expires_in` 900 |
| refresh | JSON POST `https://platform.claude.com/v1/oauth/token`, client `9d1c250a-…` | form POST `https://auth.openai.com/oauth/token`, client `app_EMoamEEZ73f0CkXaXp7hrann` | form POST `https://auth.kimi.com/api/oauth/token`, client `17e5f671-d194-4dfb-9706-5516cb48c098` |
| follower guard | `ANTHROPIC_AUTH_TOKEN` / token proxy | `CODEX_REFRESH_TOKEN_URL_OVERRIDE` blackhole | `KIMI_CODE_OAUTH_HOST` blackhole |
| shared dir | `~/shared/claude-tokens` | `~/shared/codex-tokens` | `~/shared/kimi-tokens` |

## Kimi backend (new; verified 2026-07-18 against the live endpoint)

- Endpoint/client_id/payload shape were read out of the installed kimi-code
  0.27 dist (`~/.nvm/.../@moonshot-ai/kimi-code/dist/main.mjs`), then proven:
  bogus refresh token → `400 invalid_grant`; real refresh token → `200`,
  `expires_in=900` (written back atomically).
- **TTL is 900 s**, so the claude/codex publish-on-cron model is useless for
  followers. Instead: followers pull at launch and run `ai-token kimi
  keepfresh` (pull every 300 s) for the session's lifetime; the vault does
  **refresh-on-serve** (`ai-token kimi serve`, wired into `ai-vault`'s
  `serve`/`access`, and thus into both SSH and HTTPS transports).
- Followers run with `KIMI_CODE_OAUTH_HOST` pointed at a blackhole so the CLI
  can never rotate the leader's refresh token mid-session.
- kimi-code re-reads the credentials file on every API call, so an externally
  refreshed file is picked up without a restart — this is also what makes the
  refresh-on-serve + keepfresh model work at all.

## Decisions (and why)

1. **One file with backend sections, not sourced modules.** Single-file
   install matches the tap's raw-URL distribution model; "backend module" is a
   section boundary, not a file boundary.
2. **claude backend = claude-token 2.6.4 verbatim-port** (via a mechanical
   transform, `cmd_*`→`claude_cmd_*`), including the token proxy family
   (claude-only). codex backend = codex-token 2.6.0 port. Behavior of both
   old tools is preserved; the shims mean crontabs, wrappers, and muscle
   memory needed no changes.
3. **Per-tool role semantics were NOT unified.** claude keeps
   `refreshAuthority` markers; codex keeps `.role` files. The generic layer
   unifies commands and the vault protocol, not internal role machinery.
4. **Vault is kind-generic**: composite ids `<kind>:<name>` with a registry
   (`auth_file_for`/`shared_file_for`/`publish_tool_for → ai-token <kind>`).
   `ai-vault` shells out to `ai-token kimi serve(-access)` for kimi so *all*
   kimi logic lives in one place. Owner-sync (never-rotate-on-vault) was
   generalized from claude-only to claude+kimi (`KIMI_OWNER_SYNC`,
   `refreshAuthority: "owner"` in canonical).
5. **kimi canonical for farol's own account is the live store** — the local
   kimi CLI refreshes it natively every ~15 min; `publish` copies it out.
   Other accounts' canonicals live in `~/.kimi-profiles/<p>/credentials.json`
   (owner-synced).
6. **ai-vault-http**: `parse_id` whitelist + `/sync/` guard extended to kimi;
   the claude transparent-refresh broker (`/v1/oauth/token`) stays claude-only
   (kimi followers blackhole the host by design instead).
7. The mac↔farol kimi rsync LaunchAgent (`com.kas.kimi-token-sync`) is
   superseded by the vault path (owner `sync` on the mac + refresh-on-serve
   here) once a kimi owner is enrolled; keep or retire at the owner's leisure.

## Test evidence (2026-07-18, farol)

- kimi: `check`/`status`/`publish` (shared copy has sentinel RT + fresh AT),
  sandbox `pull`, forced-stale `serve` → refresh-on-serve republishes. Real
  refresh → 200, atomic write-back.
- codex: `status --all` renders 5 profiles (roles, emails, TTLs).
- claude: `check`, `status`, `proxy-url` (registry intact),
  `CLAUDE_TOKEN_VAULT_AUTHORITY=yes claude maintain` → all 5 profiles
  republished, zero refresh events (threshold logic intact).
- shims: `claude-token`/`codex-token --version` → `ai-token 3.0.0`;
  `claude-token-proxy.service` restarted via shim (bun proxy active, ports
  400=authenticated); `codex-vault-http.service` restarted, `/healthz` ok.
