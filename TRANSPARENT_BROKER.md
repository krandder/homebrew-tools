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

### What the goal asked for: route the real OAuth refresh to a broker
The ideal hook is an OAuth token-endpoint / issuer-base override that points
Claude Code's own refresh at a broker URL. Static analysis of the Claude Code
binary found the relevant knobs:

- **`CLAUDE_CODE_CUSTOM_OAUTH_URL`** — this *is* an OAuth-endpoint override.
  When set, Claude Code rewrites `CONSOLE_AUTHORIZE_URL = $URL/oauth/authorize`,
  the token endpoint, etc. all to the custom URL. **This would be the perfect
  broker hook — but it is gated by a fixed allowlist:** the binary does
  `if (!APPROVED.includes(url)) throw Error("CLAUDE_CODE_CUSTOM_OAUTH_URL is not
  an approved endpoint.")`. The allowlist is Anthropic-controlled; we cannot add
  our broker URL. **→ blocked for our use.**
- `CLAUDE_CODE_API_BASE_URL` / `ANTHROPIC_BASE_URL` — override only the
  **inference API** host (`api.anthropic.com`), **not** the OAuth/auth endpoint.
- `forceLoginGatewayUrl` (setting, `loginMethod:"gateway"`) — the **enterprise
  OIDC gateway** device-flow login, not the standard claude.ai subscription
  refresh.

**Conclusion: Claude Code has no usable, unblocked override to redirect the
standard subscription OAuth refresh to our broker.** So the goal's fallback
applies: either a local transparent proxy, or a different transparency hook.

### Option B2 — local transparent proxy (HTTPS_PROXY + NODE_EXTRA_CA_CERTS)
Fully transparent: Claude Code keeps a real refresh token, refreshes normally,
and the call is intercepted and routed to the broker (connectors stay enabled).
**Cost:** a TLS-intercepting proxy must run on every follower + a custom CA must
be trusted; if the proxy is down, refresh fails *mid-session*. That is heavy and
fragile — the opposite of "install-and-forget."

### Option A — `ANTHROPIC_AUTH_TOKEN` (chosen)
Claude Code's auth-token mode: it is handed a credential and uses it as a normal
`Authorization: Bearer` (byte-identical to OAuth mode on the wire → same
subscription), and **never refreshes**, so it can never rotate anyone. The
follower wrapper fetches a fresh access token from the broker and sets this env.
Simple, robust (one broker HTTP call per launch; no always-on proxy), and
validated. **Tradeoff:** in auth-token mode Claude Code disables claude.ai
*connectors* and it is technically a "special env" (set by the wrapper, not by
Claude Code itself).

### Decision
The clean refresh-routing override is allowlist-blocked, and the local proxy is
too heavy/fragile for "install-and-forget." We therefore ship **Option A**
(`ANTHROPIC_AUTH_TOKEN` + broker-served fresh access tokens) as the pragmatic,
robust, install-and-forget solution, and document B2 as the upgrade path if
claude.ai connectors / full refresh transparency are later required.
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
