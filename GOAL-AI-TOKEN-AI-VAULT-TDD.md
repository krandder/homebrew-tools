# Goal: strict TDD reliability for ai-token and ai-vault

This document is the authoritative execution specification for the active
`/goal` covering `ai-token` and `ai-vault` reliability.

## Objective

Build and fully adopt a strict test-driven reliability system for `ai-token`,
`ai-vault`, and `ai-vault-http`. Convert the authentication failures observed
in Kimi session `session_97f0756d-ea86-49d9-8b86-c2931697972` into permanent
regression tests, enforce credential-lifecycle invariants, and make tested,
versioned artifacts the only route to production.

The result must protect live credentials and service continuity while proving
rotation, authority, compatibility, proxy, follower, deployment, rollback, and
recovery behavior without destructive use of production credentials.

## Scope

Included:

- `ai-token`, including Claude, Codex, and Kimi backends
- `ai-vault` and `ai-vault-http`
- compatibility shims and profile wrappers
- credential storage, refresh, publish, push, pull, sync, serve, and access
- proxy behavior and response streaming
- owner, vault-authority, and follower deployment modes
- cron, launchd, systemd, PATH, locking, and cross-host integration boundaries
- test harnesses, CI, packaging, deployment gates, rollback, and canaries

Excluded:

- `fleet-msg`
- `agents-tui`
- general tmux, CAO, fleet, or host-management redesigns
- unrelated infrastructure except minimal test/deployment interfaces
- a speculative rewrite before current behavior is characterized by tests

## Non-negotiable invariants

1. Exactly one actor may refresh a credential chain.
2. Credential generations move forward; stale or conflicting generations
   cannot overwrite newer state.
3. Empty, malformed, partial, or unauthenticated writes fail closed.
4. Every credential mutation is locked, atomic, validated, and auditable.
5. Owner-managed chains are never refreshed by the vault.
6. Vault-managed chains are never refreshed by owners or followers.
7. Followers receive usable access tokens but never functional refresh tokens.
8. Permanent failures such as `invalid_grant` stop retries and surface a clear
   `needsRelogin` state; transient failures retain bounded retry behavior.
   A 429 creates a durable per-credential and provider-wide cooldown: no
   profile may make another refresh request from that host before
   `Retry-After`, and throttling never mutates credential bytes.
9. Legacy clients cannot silently downgrade authority or credential state.
10. Running code, scheduled jobs, configuration, and installed versions must
    agree with the version that passed the release gates.

## TDD contract

Every behavioral change follows this order:

1. Commit a deterministic test that reproduces the missing or broken behavior.
2. Run it and preserve evidence that it fails for the expected reason.
3. Implement the smallest production change that makes it pass.
4. Run the complete applicable suite from a clean checkout.
5. Refactor only while the suite remains green.

A bug is not permanently fixed until its regression test is committed. Flaky
tests, unexplained skips, retry-to-green behavior, dirty generated artifacts,
and tests that depend on personal credentials are failures.

## Milestones and exit gates

### M0 — Canonical source and baseline

- Make this repository the single source for code, tests, formulas, and release
  metadata during the goal.
- Inventory installed scripts, shims, services, schedules, versions, writers,
  and deployment shapes on farol, Mac, and agent-1.
- Record current tests and known failures without changing behavior.
- Define one command for the fast suite and one for the complete suite.

Exit: the live topology can be reproduced from version-controlled artifacts,
and unversioned writers or divergent installations are explicitly known.

### M1 — Hermetic test laboratory

- Provide a mock OAuth/API server, fake clock, temporary credential stores,
  subprocess runner, concurrency controls, and restricted service PATH.
- Simulate success, expiry, rotation, `invalid_grant`, 401, 429, 5xx, gzip/SSE,
  disconnects, crashes, concurrent refreshes, and old clients.
- Keep real credentials out of destructive and fault-injection tests.

Exit: all supported credential lifecycles can be exercised locally and in CI
without network access or production state.

### M2 — Incident replay suite

Add permanent reproductions for at least these observed failure classes:

- OAuth token sent using the wrong authentication header
- compressed response decompressed while retaining `content-encoding`
- running process holding a frozen access token
- owner and vault refreshing the same rotating chain
- missing or incorrect refresh-authority marker
- stale client overwriting a newer canonical credential
- alternate refresh path bypassing the common lock
- empty or malformed shared credential write
- obsolete cron or launchd writer surviving an authority transfer
- systemd PATH resolving a different or missing executable
- old client protocol writing through an unsafe endpoint
- proxy restart, dynamic profile registration, and wrapper resolution failures

Exit: every incident fails against its historical faulty implementation and
passes against the protected implementation.

### M3 — Executable state-machine specification

- Model authority, token generation, expiry, refresh, sync, takeover, failure,
  relogin, and recovery transitions.
- Property-test the non-negotiable invariants across generated event sequences.
- Exercise concurrent writers and crash points around atomic replacement.
- Require complete transition coverage and a high mutation-test score for the
  safety-critical state machine.

Exit: injected violations are reliably detected by the suite.

### M4 — Blocking CI and release artifacts

- Run fast tests on every commit and the complete suite on every proposed
  production change.
- Block merge and release on failures, flakes, skips, missing red-test evidence,
  or artifact drift.
- Produce immutable, checksummed artifacts from a clean commit.
- Keep formulas and installed compatibility shims tied to the same release.

Exit: an untested or locally modified production artifact cannot pass the
normal release path.

### M5 — Production-shaped canary and rollout

- Exercise farol as vault authority, Mac as owner/follower, and agent-1 as
  follower using disposable profiles and stores.
- Inspect actual services, schedules, process environments, ports, versions,
  and hidden writers before promotion.
- Promote through staging, a dedicated live canary profile, limited rollout,
  post-deploy verification, and timed soak.
- Prove rollback using the same packaging and deployment path.

Exit: the complete lifecycle and rollback pass in the deployed environment
without exposing a human profile to destructive tests.

### M6 — Continuous verification and 30-day soak

- Run hermetic lifecycle tests continuously in CI.
- Run a small live canary on a dedicated profile at an approved cadence.
- Retain versioned evidence and alert on the first failed invariant or lifecycle
  transition.
- Measure cross-host version convergence and unexpected credential writers.

Exit: 30 consecutive days of green scheduled canaries, no unresolved credential
incident, no unversioned writer, and a final restore/rollback drill.

## Deployment and emergency policy

Normal production path:

`clean commit -> CI -> immutable artifact -> staging -> canary -> limited rollout -> post-deploy verification -> soak`

Break-glass restoration may be used to recover an outage. It must produce an
audit record and rollback plan, and no subsequent release may proceed until the
incident has a committed failing-then-passing regression test.

## Decisions requiring Kelvin

Recommended defaults are recorded so work can proceed once approved:

- Canonical repository: keep `krandder/homebrew-tools` for this goal.
- Legacy writers: reject unsafe/unversioned mutations and disable obsolete jobs.
- Live canary: use a dedicated non-human Claude profile with minimal allowance.
- Production promotion: Kelvin approval until the 30-day soak completes.
- Emergency changes: allow break-glass restoration under the policy above.
- Refactoring: characterize first; permit only incremental, test-backed changes.

Kelvin approved the canonical repository, hermetic laboratory, incident replay,
broad state-machine coverage, hard CI, production-shaped verification, and
controlled release phases on 2026-07-20. The dedicated canary profile remains
the only required designation.

## Post-characterization implementation language

The recommended migration target is typed Python 3 using the standard library
for the control plane. The current Bash already delegates sensitive JSON,
locking, and mutation work to embedded Python, while `ai-vault-http` is Python.
Consolidating there removes shell quoting and PATH boundaries without adding a
new runtime. Keep the small Bun proxy boundary until its transport behavior is
fully characterized. Consider Go only if evidence later requires a single
static binary or materially higher concurrency.

## Definition of done

The goal is complete only when:

- every applicable incident from the Kimi session has a permanent replay test;
- all credential authority and rotation invariants are executable and green;
- CI blocks unsafe merges and releases;
- production artifacts are traceable to clean commits and checksums;
- farol, Mac, and agent-1 pass the deployment matrix;
- rollback has been exercised successfully;
- no unsafe legacy or unversioned writer remains; and
- scheduled canaries remain green for 30 consecutive days.
