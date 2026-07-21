# Goal completion audit v3 — 2026-07-21

This audit treats completion as unproven and supersedes only the status
conclusions in `completion-audit-2026-07-20-v2.md`. Historical findings and
failed evidence remain retained. The authoritative goal is
`GOAL-AI-TOKEN-AI-VAULT-TDD.md`.

## M0 — canonical source and baseline: proved

- `krandder/homebrew-tools` remains the protected canonical source for code,
  tests, formulas, deployment assets, and release metadata.
- The original three-host topology and legacy writers are recorded in
  `baseline-2026-07-20.md` and `physical-fleet-inventory-2026-07-20.md`.
- `tests/run fast` and `tests/run full` are the declared local gates.
- The selected runtime on all three hosts is immutable release
  `961817df7012-cdcf26652e0e`, built from commit
  `961817df7012a82fa6ff956ed60f77c542c21c57` and tree
  `521e60cd520982d33ca66f2a9e3e0b2cfbd005b3`.

## M1 — hermetic laboratory: proved

The complete suite uses disposable homes and credential stores, loopback OAuth
and API servers, fake time, subprocess fixtures, restricted PATHs, concurrency
barriers, crash injection, compressed and streaming responses, disconnects,
legacy clients, generated wrappers, and simulated leader/follower transports.
It makes no real provider request and uses no production credential. The
current executable inventory is described in `tests/README.md`.

## M2 — incident replay: proved

`kimi-incident-replay-audit-2026-07-21.md` maps every named recurring failure
class to executable tests. That replay also exposed and permanently fixed three
previously overstated guarantees: in-place Claude credential writes, formula
source drift, and umask-dependent release bytes. Later red-first audits closed
all remaining credential, authority, predictable-path, generated-entrypoint,
audit, authorization, deployment, checksum, and HTTP snapshot writers.

## M3 — executable state machine: proved

The reference model exercises every declared authority, generation, expiry,
refresh, publish, cooldown, takeover, relogin, recovery, and follower
transition. It runs 20,000 generated event steps and kills all 18 selected
safety mutants, with 0 survivors. Implementation tests separately exercise
concurrent writers and atomic-replacement crash points. See
`state-model-mutation-2026-07-20.md`.

## M4 — hard CI and immutable release: proved

- Protected `main` requires strict `release-gate`; administrators are covered,
  and force pushes and branch deletion are disabled.
- Production-changing pull requests must preserve a runnable test-only commit
  that fails before the implementation commit passes.
- PR #48 passed both protected release gates, and protected-main run
  `29839659857` passed 205 Python tests plus four shell integration suites.
- Its 32-file artifact has an external checksum, exact commit/tree manifest,
  normalized modes, member digests, and exact source-byte verification. GitHub
  retains it through 2026-08-20 under the enforced 30-day policy.
- Formula sources name immutable reachable commits and match their pinned
  checksums and release members.

## M5 — production-shaped rollout: proved

Farol leader/vault, agent-1 follower, and the dedicated macOS UID-502 follower
each completed exact installation, verification, rollback to
`f41bcf7bddab-81d3623997b5`, old-release verification, restoration, and final
new-release verification. Only isolated `canary-claude` state participated.
All three then passed the exact live role lifecycle on the selected release;
the records and artifact proof are in
`atomic-generated-state-promotion-2026-07-21.md`.

As of this audit, all three configs are regular mode-0600 files and name the
same profile and full runtime commit. Every deployed Linux service/timer and
each macOS dispatcher, UID-switch wrapper, and canary-owned run wrapper matches
the selected release asset byte-for-byte. The isolated vault and all Linux
timers are enabled and active; the macOS dispatcher is loaded with last exit
zero and its activation marker is mode 0600.

## M6 — continuous verification and soak: active, not complete

Proved now:

- lifecycle schedules are enabled on all three hosts;
- every run verifies its exact installed release before provider activity;
- linked mode-0600 schema-3 evidence detects unexpected writers and retains
  failures rather than retrying them away;
- atomic collection retained all 60 records present at promotion time;
- the daily cumulative auditor is enabled and correctly reports
  `no completed soak day` before July 22 is complete; and
- failures route through the authenticated sanitized incident path.

Still required by real time and therefore not yet proved:

1. Successful scheduled evidence for farol leader, agent-1 follower, and macOS
   follower on every UTC day from 2026-07-22 through 2026-08-20, with no failed
   lifecycle or invariant record in that window.
2. A successful scheduled post-window anchor for every host/role on
   2026-08-21 UTC.
3. The final retained-evidence verification over all 30 days.
4. A final incident audit and exhaustive state-writer audit showing no
   unresolved credential incident or unsafe unversioned writer.
5. A final physical three-host rollback, old-release verification, restore,
   and exact current-release verification after the soak.

The goal must remain active until all five items have actual evidence. The
earliest completion evaluation is 2026-08-21 UTC; simulated time or manual
runs cannot satisfy any scheduled-day requirement.
