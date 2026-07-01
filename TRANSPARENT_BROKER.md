# Transparent OAuth refresh broker — architecture decision

## Goal
Claude Code (and codex) run **completely normally** on every machine with zero
awareness of the vault. Log in on any one machine; every machine's claude/codex
just works, with no client-side refresh ever rotating/invalidating another.

## Why the current (sentinel + blackhole) approach fails the goal
- Followers run with a **sentinel (fake) refresh token** + a **blackholed refresh
  endpoint**. When the access token expires, the client tries to refresh, the
  refresh fails, and the client **knows something is wrong** ("please log in").
  That violates "works normally / no awareness."
- Claude has no refresh-endpoint override env, so we can't cleanly blackhole it.
- Every client/session refreshing individually causes Anthropic token-endpoint
  rate-limits and the mutual invalidation we set out to avoid.

## The transparency hook (from static analysis of the Claude Code binary)
Claude Code has distinct auth modes:
1. **OAuth / claude.ai account** — `/login`; short-lived access + rotating
   refresh token. **This is the source of the invalidation problem.**
2. **Auth-token / API-key** — credential supplied externally via
   `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, or the `apiKeyHelper` setting.
   In this mode **Claude Code does not perform OAuth refresh at all**.

Key fact (confirmed from the binary): `ANTHROPIC_AUTH_TOKEN` is sent as
`Authorization: Bearer <token>` — **byte-identical on the wire** to what OAuth
mode sends. Therefore an OAuth access token supplied via `ANTHROPIC_AUTH_TOKEN`
authenticates the **same claude.ai subscription** (same account, same billing),
but Claude Code **never refreshes it**, so it can **never rotate or invalidate**
the leader's refresh token. Anthropic cannot tell the modes apart on the wire.

## Chosen design: broker-served fresh access tokens via ANTHROPIC_AUTH_TOKEN
- **Broker (leader = farol)** is the **sole owner** of the real refresh token. It
  refreshes **once per access-token TTL (~hours)** — not per client, not per
  launch — and serves the current fresh access token over the existing
  `vault.ekelvin.com` HTTPS endpoint.
- **Followers** run a thin `claude` wrapper (`~/bin/claude`) that, before each
  launch, fetches the current access token from the broker and runs the real
  `claude` with `ANTHROPIC_AUTH_TOKEN=<access> exec claude`.
- Claude Code on the follower is in **auth-token mode**: it uses the supplied
  bearer, does **no refresh**, has **no knowledge of the vault**, and runs
  exactly as normal. The refresh token never exists on a follower.

## Why this is strictly better
| | sentinel + blackhole (old) | broker + ANTHROPIC_AUTH_TOKEN (new) |
|---|---|---|
| Client awareness | knows it's broken when access expires | none — runs normally |
| Refreshes to Anthropic | per session (rate-limit storms, invalidation) | **1 per TTL, by the broker only** |
| Refresh token on followers | sentinel (hack) | **absent** |
| Claude-specific override needed | yes (none exists) | no — standard auth mode |
| Robust to access expiry | breaks until leader republishes | wrapper pulls fresh on each launch |

## Implementation plan
1. **Broker access endpoint**: extend `codex-vault-http` with
   `GET /access/<kind>/<name>` → returns the **current fresh access token** (no
   refresh token) for a profile. The leader's existing publish step already
   refreshes; this just exposes the access token. (Auth: same bearer-token ACL.)
2. **Follower wrapper** (`claude`, `codex`): on launch, `curl
   $BROKER/access/...`, set the credential env (`ANTHROPIC_AUTH_TOKEN` for claude;
   codex keeps its working model or adopts the same), `exec` the real binary.
3. **Bootstrap**: log in on one machine → push the refresh token to the broker
   (existing `push`/`receive`). The broker owns it forever after.

## The one validation (safe — does NOT hit the token endpoint)
Run a single `claude -p "…"` with `ANTHROPIC_AUTH_TOKEN` set to the mac's current
access token. This calls the **inference** endpoint (api.anthropic.com), **not**
the OAuth token endpoint, so it cannot worsen the refresh rate-limit. Success
confirms auth-token mode preserves subscription access — the only open
assumption in this design.

## Non-goals / notes
- Codex already works (sentinel + blackhole, long TTL). It can later adopt the
  same broker model for uniformity, but it's not required.
- This depends only on standard OAuth (refresh_token grant) + Claude Code's
  documented auth-token mode — no Anthropic-specific behavior beyond that.
