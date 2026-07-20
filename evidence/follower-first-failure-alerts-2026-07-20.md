# Follower first-failure alerts — 2026-07-20

The completion audit found a real lifecycle gap: farol had a local systemd
`OnFailure` incident unit, but agent-1 had no failure unit and the macOS
dispatcher only retained stdout/stderr. A failed follower invariant therefore
could remain unnoticed until manual evidence review.

## Red

Commit `fa0951b` added three contracts before implementation:

- a follower reporter must send only a fixed sanitized failure schema and must
  never forward arbitrary evidence fields;
- the authenticated vault must reject human profiles, durably retain the alert,
  and invoke the incident pipeline; and
- agent-1 and macOS schedules must invoke that reporter while macOS preserves
  the original lifecycle failure status.

The focused run failed with a missing reporter, HTTP 404 for the absent route,
and missing release/scheduler assets. Those failures reproduce the gap.

## Green

Commit `1b44820` adds `tools/report-canary-failure`, authenticated
`POST /canary-alert`, a packaged agent-1 `OnFailure` service, and a macOS
failure branch. The client whitelists host, role, non-human `canary-*` profile,
full release commit, failed phase/return code, and evidence basename. The server
validates that exact schema, caps the request size, stores a mode-0600 record,
and invokes the configured incident emitter without a shell. Arbitrary evidence
fields and human profile names never enter the alert record or notification.

The focused alert, deployment, HTTP, and deterministic-artifact suites passed.
The complete hard gate then passed all Python suites and four shell integration
suites, including follower/leader matrices, refresh concurrency and persistent
provider-wide rate-limit cooldown invariants. Physical activation of this path
must use the protected post-merge artifact; no live service or dormant timer was
changed by this red/green cycle.
