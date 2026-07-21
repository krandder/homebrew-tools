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
controlled release phases on 2026-07-20. He designated `canary-claude`, isolated
homes on farol and agent-1, and the dedicated macOS account/keychain
`ai-token-canary`. Protected runtime commit
`bdbd1babd9f8208cd1ff2f40fab4d1016855aca0` is installed and verified on all
three hosts, and physical rollback/restore was exercised on each. The separate
Anthropic account is `ai@futarchy.ai` with a Claude Max entitlement. Its OAuth
credential is canonical only in the isolated farol vault; followers receive a
sentinel refresh token. Farol leader, agent-1 follower, and the dedicated macOS
follower all passed their live lifecycle on the protected runtime. A real
agent-1 inference through the isolated launcher also passed.

M0 through M5 are complete. M6 is active: the Linux timers and the macOS
dispatcher activation marker were enabled on 2026-07-21 UTC, and each scheduled
entrypoint passed once. The farol leader publishes every two hours so the
approved 15-minute agent-1 consumer cannot outlive an access-token generation;
publishes with more than 2.5 hours remaining make no refresh request, and all
actual refresh attempts remain behind the provider-wide cooldown. The agent-1
and macOS lifecycle canaries remain daily. The first Mac run found a
fresh-Keychain failure before
the intended fallback account could create the Claude item. Pull transport had
already returned a fresh sentinel-only credential; `security` then exited 44
for the expected missing item and `set -euo pipefail` aborted. PR #19 preserved
the failing regression commit before the one-line fix, passed hard CI, and was
promoted as an immutable release. The pre-fix failure remains in the
evidence chain. PR #21 subsequently proved that the soak verifier accepted
mixed immutable artifact IDs, then made exact release convergence blocking and
was promoted across the same three-host matrix. PR #23 then proved the daily
leader cadence could not keep the approved 15-minute consumer inside an
eight-hour access-token generation and changed only the leader timer to every
two hours. Release `699237941a26-a25d9f0a55dd` was installed, selected, and
live-checked on all three hosts; a one-day three-record matrix passed the exact
commit and artifact convergence gate. PR #27 then made scheduler provenance,
safe-record linkage, and post-window anchors mandatory. PR #28 replaced the
Mac's nonexistent-file continuity check with metadata from the real dedicated
Keychain. Release `253597d3255e-052616a82b39` was installed, selected, and
manually live-checked on all three hosts; the Mac passed both the one-time
legacy snapshot migration and a subsequent Keychain-to-Keychain continuity
cycle. The first genuinely unattended scheduler-native matrix then passed at
04:00, 04:10, and 04:20 UTC on the same release. PR #34 then corrected the
farol failure unit's unsupported incident category, passed protected CI, and
repeated exact rollback/restore plus manual lifecycle verification on all
three hosts. A real explicit agent-1 pull outside the lifecycle runner was
retained as a `writer-continuity` failure before the designated runner
re-established the chain; the consumer wrapper itself reads a temporary vault
response and does not write the monitored credential. The clean 30-day window
is pinned to release `bdbd1babd9f8-102ff6b0110f` from
2026-07-22 through
2026-08-20 UTC, with the final gate eligible on 2026-08-21 UTC.

The immutable release now includes a fail-closed live-canary runner. It requires
an explicit designation for a non-human `canary-*` Claude profile,
pins all lifecycle commands to a verified installed commit, replaces ambient
`HOME` with the dedicated canary home, and retains only sanitized mode-0600
step evidence. Linux uses schema 1. A macOS follower uses schema 2 and must name
an `ai-token-canary*` OS user; the runner verifies the kernel UID resolves to
that exact user and that its password-database home is the configured canary
home before touching the process-wide Claude Keychain service. Directory-only
isolation or merely changing `HOME` is rejected.

The release also includes `verify-live-soak`, the executable M6 accounting
gate. It requires 30 complete UTC days by default, an explicit set of required
host/role pairs, one converged profile, release commit, and immutable artifact
ID, exact successful leader/follower step sequences, and mode-0600 non-symlink
evidence. Any failed
record in the window fails the gate even if a later retry succeeds. This proves
the eventual soak only after real scheduled evidence exists; it does not start
or simulate the live 30-day clock.

The operator-only `collect-live-soak` command atomically collects every retained
record from the fixed farol, agent-1, and dedicated macOS locations before the
verifier runs. It refuses partial output, unsafe tar members, permissive modes,
AppleDouble files, duplicate names, or invalid JSON and writes a mode-0600
source/count/digest manifest. It is canonical source but not canary runtime, so
improving the collection boundary does not change the pinned soak release.

The release candidate also contains a daily cumulative audit for the failure
mode that lifecycle `OnFailure` cannot observe: a timer or host that never runs.
At 04:40 UTC, after all three next-day anchors, it uses the existing collector
and verifier to check every completed qualifying day. A missing record, failed
record, chain break, writer drift, release mismatch, or missing anchor exits
nonzero through the existing canonical incident unit. Before the first day is
complete it is a no-op. This adds no credential access or alternate evidence
writer.

Canary evidence schema 3 measures unexpected writers without reading or
hashing credential contents. Each run records whether its entrypoint was
scheduled or manual, a SHA-256 link to the previous sanitized evidence record,
and only existence, size, inode, mtime, ctime, and mode before and after the
designated lifecycle command. A manual success cannot satisfy a scheduled day.
An omitted record breaks the chain, and one successful scheduled record after
the window anchors each host/role tail before the gate can pass. The next run
must begin from the previous final metadata or it fails before release
verification; the 30-day verifier independently checks the complete per-host
chain. On macOS the runner inspects only the dedicated Keychain item's account
and creation/modification timestamps; it never requests the password. The
legacy nonexistent-file snapshot may transition to this real Keychain metadata
once, after which any between-run Keychain change fails closed. Existing file
credentials must be regular mode-0600 files. Scheduler-native
nonzero exit and `OnFailure`/incident wiring remain the deployment alert path.
The follower alert path is authenticated and sanitized; a real agent-1
fail-closed pull produced a mode-0600 vault alert and a canonical incident.
The physical deployment, later promotions, and incident-routing correction are
recorded in `evidence/physical-canary-deployment-2026-07-20.md`,
`evidence/canonical-release-promotion-2026-07-20.md`, and
`evidence/canonical-incident-routing-2026-07-20.md`. Credential activation and
the M6 clock are recorded in
`evidence/live-canary-activation-2026-07-21.md`; the post-unattended alert audit,
taxonomy fix, final pre-window promotion, and real writer-continuity detection
are recorded in
`evidence/post-unattended-incident-audit-2026-07-21.md`. Failed pre-activation,
pre-fix, and activation-day records remain retained and do not count toward the
clean window.

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
