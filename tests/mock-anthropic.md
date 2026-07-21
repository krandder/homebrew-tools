# Mock Anthropic — behavioral playbook for tests

Everything we learned about how api.anthropic.com (and platform.claude.com)
actually behave, distilled from the 2026-07-20/21 live investigation so our
stubs can reproduce the real edge cases instead of happy paths. Scope:
claude messages API + OAuth/entitlement endpoints. (Codex Responses API and
kimi notes at the end.)

## 1. The genuine Claude Code request shape (what the gate checks)

POST /v1/messages?beta=true from a real CLI (2.1.x) carries ALL of:

- **body**: model, max_tokens 64000, stream: true,
  `thinking: {"type":"adaptive","display":"omitted"}`,
  `output_config: {"effort":"low"}`,
  `metadata.user_id`: a JSON **string** containing
  `{"device_id":"<64-hex>","account_uuid":"<uuid>","session_id":"<uuid4>"}`,
  `system` (list of blocks), ~33 `tools`,
  `context_management: {"edits":[{"type":"clear_thinking_20251015","keep":"all"}]}`,
  messages.
- **headers** (order-preserving stack; several are load-bearing):
  `authorization: Bearer <AT>`,
  `anthropic-version: 2023-06-01` (missing → 400 invalid_request_error),
  `anthropic-beta` — full flag list;
  **`oauth-2025-04-20` is present ONLY for OAuth/subscription-auth requests**
  (absent for API-key traffic — the entitlement resolver uses it to choose
  plan-inclusion vs credits metering);
  `extended-cache-ttl-2025-04-11` sometimes appended;
  `fallback-credit-2026-06-01` present but not load-bearing (verified).
  `x-app: cli`, `x-claude-code-session-id: <uuid per session>`,
  `x-stainless-arch/-lang/-os/-package-version/-retry-count/-runtime/-runtime-version/-timeout`,
  `user-agent: claude-cli/<ver> (external, sdk-cli)`,
  `anthropic-dangerous-direct-browser-access: true`, `accept: application/json`.

**Lesson L1**: a bare {model, messages} body with a valid AT is NOT equivalent
traffic. Entitlement-sensitive behavior (429s) only reproduces when the stub
(or the test client) sends the full shape. Fixture: fleet repo
`tokens-dashboard/usage/fixtures/cli-shape.json`.

## 2. CLI startup call sequence (mock these endpoints)

HEAD / (→ 404, that's expected), then before the first /v1/messages:

1. `POST /api/eval/sdk-<stable-id>` — feature-flag eval. Body:
   `{"attributes": {"id","sessionId","deviceID","platform",
   "organizationUUID","accountUUID","userType","subscriptionType",
   "rateLimitTier","organizationRole","subscriptionCreatedAt",
   "firstTokenTime","appVersion","entrypoint"},
   "forcedVariations": {}, "forcedFeatures": [], "url": ""}`
   → 200 `{"features": {...}}`.
2. `GET /api/claude_cli/bootstrap?entrypoint=sdk-cli&model=<m>` — entitlement
   payload: `client_data.cedar_lagoon: {"claude-fable": true, ...}`,
   `cedar_basin: <date>`, `additional_model_options: [{model, name,
   disabled_reason}]`.
3. `GET /api/oauth/account/settings` (onboarding flags;
   `enabled:false, disabled_reason:"extra_usage_disabled"` for the credits pool),
   `/api/claude_code_grove`, `/api/claude_code_penguin_mode`,
   `/v1/mcp_servers?limit=1000`, public `/mcp-registry/...` (400 if the
   Authorization header is malformed; fine without).
4. Then `POST /v1/messages?beta=true`.

**Lesson L2**: replaying these calls with another account's token does NOT
bless it (verified: bootstrap+eval → still 429). They are registration/
telemetry, not arming. A mock can return canned 200s for all of them.

## 3. The entitlement gate (the July-20 incident model)

Observed, reproducible rules for premium models (fable/opus/sonnet):

- **[R1] Genuine CLI shape required.** Minimal bodies → 429 even with a
  perfectly valid AT and plan. Haiku (`claude-haiku-4-5-*`) is EXEMPT —
  always 200. Use haiku as the "everything-else-works" control in tests.
- **[R2] Account-tier gate.** With identical shape and valid tokens, one
  account can get 200 while another gets 429 — and the bootstrap endpoint
  STILL says `claude-fable: enabled: true` for the blocked account. The
  server can be self-inconsistent: bootstrap-truth ≠ messages-truth.
- **[R3] Token-class gate.** Tokens minted by the genuine CLI runtime
  (its own refresh at startup) pass with genuine shape; the same account's
  login-issued AT or script-refreshed AT fails with the same shape.
  The CLI does NOT persist runtime-refreshed tokens to disk.
- **[R4] Interactive `/login` lineage works in the genuine CLI** — a fresh
  browser-OAuth login + real CLI run passes. This is the "restart fixes it"
  mechanism from Anthropic's own incident note.
- 429 body: `{"type":"error","error":{"type":"rate_limit_error",
  "message":"This request would exceed your account's rate limit. Please
  try again later."}}` (or just `"message":"Error"`).
- The CLI's user-facing version of R2/R3: `You've reached your Fable 5 limit.
  Run /usage-credits to continue or switch models with /model.`

**Lesson L3**: a good mock implements R1–R4 as independent toggles
(shape-strict on/off, per-account allow/deny, per-token-class allow/deny),
because production flips them independently. Our stub upstream must be able
to 429 per (model class × shape × account × token class), not just per token.

## 4. OAuth / tokens

- Refresh: `POST https://platform.claude.com/v1/oauth/token`
  (form: grant_type=refresh_token, client_id, refresh_token)
  → `{access_token, refresh_token, expires_in: 28800, scope?}`.
  **Cloudflare-fronted**: non-browser-ish clients can get `403 error code:
  1010` (bot management). ai-token's refresh passes; bare curl does not.
- AT TTL 8h (28800s). **RT rotates every refresh**; reusing a consumed RT →
  `invalid_grant` / "refresh token has already been used to generate a new
  access token" (codex: same semantics, error `refresh_token_reused`).
- `GET /api/oauth/claude_cli/roles` → `{organization_uuid, organization_role}`.
- `GET /api/oauth/profile` → account/org (uuid, email, organization_type,
  rate_limit_tier, seat_tier, has_extra_usage_enabled, billing_type).
- `GET /api/oauth/usage` →
  `{five_hour: {utilization, resets_at}, seven_day: {...}, limits:
  [{model, percent, is_active}], credits/...}` — during the incident it
  returned degenerate `{utilization: 0, resets_at: null}` for most profiles.
  **Lesson L4**: mocks should be able to emit null resets + zeroed
  utilization; dashboards must render "—" not crash.

## 5. Responses & usage accounting

- Non-stream: full JSON `{id, model, content:[{type:text,text}], usage:
  {input_tokens, output_tokens, cache_read_input_tokens,
  cache_creation_input_tokens, cache_creation:{ephemeral_5m_input_tokens,
  ephemeral_1h_input_tokens}}}`.
- SSE stream: `message_start` (message{id,model,usage incl. input+cache}),
  `content_block_delta` (text fragments), `message_delta`
  (`usage.output_tokens`, cumulative), `message_stop`. Untagged cache
  creation counts as 5m TTL by convention.
- Retry-on-429: the CLI retries (x-stainless-retry-count increments) and
  eventually surfaces; proxies should cool the account (our classes:
  401→900s, 429→1800s, 5xx→300s) and fail over the same request.
- `GET /v1/models` lists model ids (only `claude-fable-5` for fable).

## 6. Codex (Responses API) notes for the codex mock

- `usage.input_tokens` **includes** cached tokens; net input =
  input_tokens − `input_tokens_details.cached_tokens` (double-charging this
  was a real $2.6k/day dashboard bug).
- SSE ends with `response.completed` carrying the full response object
  `{id, model, usage}`; the codex backend REQUIRES `stream: true` and
  list-shaped `input`.
- Model gating is per-account: `{"detail":"The 'gpt-5-codex' model is not
  supported when using Codex with a ChatGPT account."}` — the mock should
  reject wrong models with this exact shape.
- wham/usage: `{rate_limit: {primary_window: {used_percent,
  reset_after_seconds}, secondary_window: {...}}}`.

## 7. Kimi (OpenAI-style) notes

- `usage` on the final chunk only when `stream_options.include_usage`;
  non-stream bodies carry it always. `prompt_tokens` includes cached
  (`prompt_tokens_details.cached_tokens`).

## 8. Mock implementation checklist for our suites

1. Full-shape validation mode: reject minimal bodies on premium models with
   the R1 429 body; always accept haiku.
2. Per-account plan registry: allow/deny per (account × model class), with
   bootstrap returning `enabled:true` even for denied accounts (R2
   inconsistency).
3. Token classes: login-issued / script-refresh / cli-refresh tokens with
   independent allow rules (R3).
4. Rotating RTs: each refresh returns a new RT; replayed old RT →
   invalid_grant.
5. Degenerate modes: null resets, zeroed utilization, 529 overload,
   intermittent-then-recovering 429s (for cooldown-expiry tests).
6. Fingerprint simulation: platform.claude.com returns 403/1010 to
   non-CLI user agents (so refresh-path tests exercise the real wall).
7. SSE fidelity: message_start/message_delta output_tokens cumulative —
   our usage tap parses exactly these.
