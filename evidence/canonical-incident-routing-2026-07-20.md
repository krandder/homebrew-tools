# Canonical incident routing from the isolated vault — 2026-07-20

This evidence contains no credential or pairing secret.

## Physical failure found

After protected commit `8ba65cfc395405d9e6b0375af603a91af3213380`
was promoted, agent-1's dormant lifecycle unit was started manually. It failed
closed at the expected `pull` step because no canary credential has been
published. Its new `OnFailure` unit completed successfully, the vault accepted
`POST /canary-alert`, and a mode-0600 sanitized alert record was retained.

The live verification then found that the incident emitter inherited
`HOME=/home/kelvin/.ai-token-canary`. It consequently wrote the incident into
the isolated canary `.openclaw` tree instead of the canonical incident tree.
The restricted service `PATH` also omitted the installed OpenClaw CLI used by
the emitter's notification step. HTTP success therefore did not prove an
actionable canonical alert.

## Red and green

Commit `57aa1ae` added a failing contract requiring the isolated vault unit to
be a release payload and to pin all of these boundaries explicitly:

- isolated canary `HOME` and release-selected `ai-vault-http`;
- canonical `OPENCLAW_STATE_DIR`;
- the canonical incident emitter; and
- the OpenClaw CLI directory in `PATH`.

The focused test failed because no canonical vault service asset existed.
Commit `0334e6a` adds the exact unit under `deploy/canary/farol/` and includes it
in the immutable release manifest. The deployment and deterministic artifact
suites passed, followed by the complete Python and four-shell-suite hard gate.

## Physical confirmation

The isolated physical service was corrected to the specified environment and
restarted healthy. A second manual agent-1 lifecycle run again failed closed at
`pull`; its alert unit completed successfully, the vault returned HTTP 200,
and `data/incidents/2026-07-20.jsonl` in the canonical OpenClaw workspace gained
the sanitized `health-check-fail` incident for agent-1. The notification CLI
was present on the service's explicit path. The shared incident emitter does
not expose downstream Telegram delivery status, so the machine-verifiable
boundary is canonical incident retention plus a completed emitter invocation.

The agent-1 timer remained disabled throughout. The physical service hotfix
must be replaced byte-for-byte by the protected post-merge artifact before the
deployment boundary is considered converged.
