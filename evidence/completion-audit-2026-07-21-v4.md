# Goal completion audit v4 — 2026-07-21

This audit treats completion as unproven and supersedes only the status
conclusions in `completion-audit-2026-07-21-v3.md`. Historical failures and
promotion evidence remain retained. The authoritative specification is
`GOAL-AI-TOKEN-AI-VAULT-TDD.md`.

## M0 — canonical source and baseline: proved

- `krandder/homebrew-tools` remains the protected canonical source for code,
  tests, formulas, deployment assets, and release metadata.
- The original three-host topology and legacy writers remain recorded in
  `baseline-2026-07-20.md` and `physical-fleet-inventory-2026-07-20.md`.
- `tests/run fast` and `tests/run full` are the declared local gates.
- Canonical `main` documentation commit `459ff042c61d46ebb123a890946060a287f8f780`
  passed protected-main run `29855598092`. Runtime is deliberately pinned to
  the last protected production merge rather than later documentation commits.

## M1 — hermetic laboratory: proved

The complete suite uses disposable homes and credential stores, loopback OAuth
and API servers, fake time, subprocess fixtures, restricted service PATHs,
concurrency barriers, crash injection, compressed and streaming responses,
disconnects, legacy clients, generated wrappers, and simulated cross-host
leader/follower transports. It performs zero real provider calls and does not
read or mutate personal credential stores. `tests/run-unittest` makes skips
and expected failures nonzero suite results.

## M2 — incident replay: proved

`kimi-incident-replay-audit-2026-07-21.md` maps every incident class named in
the goal to permanent executable tests. Later red-first audits closed every
credential, authority, rate-limit, predictable-path, generated-entrypoint,
audit, authorization, deployment, checksum, wrapper, mirror, proxy, and HTTP
snapshot defect discovered during completion review.

## M3 — executable state machine: proved

The reference model covers every declared authority, generation, expiry,
refresh, publish, cooldown, takeover, relogin, recovery, and follower
transition. It executes 20,000 generated steps and kills all 18 selected
safety mutants with zero survivors. Implementation tests independently cover
concurrent writers and atomic-replacement crash points. See
`state-model-mutation-2026-07-20.md`.

## M4 — hard CI and immutable release: proved

- Protected `main` requires strict `release-gate`, enforces administrators,
  and forbids force pushes and branch deletion.
- Production pull requests must contain a preceding test-only commit whose
  complete suite is deterministically red. Every file in `tests/` is protected
  from the paired production commit, merge commits are rejected, and every
  production commit consumes its own red proof.
- The current gate runs 220 Python tests and four shell integration suites;
  skips and expected failures are failures.
- PR #59 branch/PR runs `29851166091` and `29851167785`, followed by protected
  runtime run `29851486177`, passed.
- Runtime commit `6201b1920093cc605c7e04840c967407ae24d644`, tree
  `7a1614d9b39bdf7a524aee753a430cb9065459bb`, is immutable release
  `6201b1920093-f8bd4e418821`. Its 42-file archive SHA-256 is
  `f8bd4e418821d5cf6cd6c17e15e027da7b3e5ac0747549d52448795086bc5641`.
- The artifact contains every scoped `ai-any` healing wrapper, mirror, and
  proxy; `ai-any` is executable. Every formula resource names an immutable
  reachable commit and matches its checksum and current canonical bytes.

## M5 — production-shaped rollout: proved

Farol leader/vault, agent-1 follower, and dedicated macOS UID 502 each
installed and exactly verified the 42-file release, rolled back to
`ed994de4434e-5179f403c404`, verified that old release, restored, and verified
the current release again. Only isolated `canary-claude` state participated.

All three role lifecycles passed on the selected release. The final manual
records are listed in `complete-scoped-interface-promotion-2026-07-21.md`; the
existing Farol timer then produced linked scheduled record
`20260721T180000.055258Z-farol-leader-56855.json` with exact successful
verify/publish steps. Every live Linux unit and Mac plist/UID-switch/run wrapper
was rechecked byte-for-byte against the selected artifact. All configs are
regular mode-0600 files naming the same profile and full runtime commit.

## M6 — continuous verification and soak: active, not complete

Proved now:

- lifecycle schedules are enabled on all three hosts;
- every lifecycle verifies its selected release before provider activity;
- linked mode-0600 schema-3 evidence retains failures and detects unexpected
  writers without credential contents or credential hashes;
- atomic collection currently retains all 74 records: 28 Farol, 23 agent-1,
  and 23 macOS;
- all four records on the final pin are successful and chain-valid;
- the daily cumulative auditor is enabled and correctly reports
  `no completed soak day` before July 22 is complete; and
- failures route through the authenticated sanitized incident path.

Still required by real time and therefore not yet proved:

1. Successful scheduled evidence for Farol leader, agent-1 follower, and macOS
   follower on every UTC day from 2026-07-22 through 2026-08-20, with no failed
   lifecycle or invariant record in that window.
2. A successful scheduled post-window anchor for every host/role on
   2026-08-21 UTC.
3. Final retained-evidence verification over all 30 days.
4. A final incident audit and exhaustive state-writer audit showing no
   unresolved credential incident or unsafe unversioned writer.
5. A final physical three-host rollback, old-release verification, restore,
   and exact current-release verification after the soak.

The goal must remain active until all five items have actual evidence. The
earliest completion evaluation is 2026-08-21 UTC; simulated time or manual
runs cannot satisfy a scheduled-day requirement.
