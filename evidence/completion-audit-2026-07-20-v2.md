# Goal completion audit v2 — 2026-07-20

This audit treats completion as unproven and checks each milestone against the
current repository, protected CI, immutable artifacts, and deployed hosts. It
supersedes the status conclusions in `goal-coverage-audit-2026-07-20.md`.

## M0 — canonical source and baseline: proved

- `krandder/homebrew-tools` is the protected canonical repository.
- `baseline-2026-07-20.md` and `physical-fleet-inventory-2026-07-20.md` record
  the original installed scripts, writers, services, and schedules.
- `tests/run fast` and `tests/run full` are the declared local commands.
- Deployment code, scheduler definitions, the isolated vault unit, formulas,
  shims, and release metadata are version controlled and artifact-pinned.

## M1 — hermetic laboratory: proved

The suite uses disposable homes/stores, local OAuth and HTTP servers, fake
time, subprocess fixtures, restricted PATHs, concurrency barriers, crash
points, compressed/SSE responses, disconnects, legacy clients, wrappers, and
cross-host simulations. The complete gate performs no real provider call and
uses no production credential. Relevant evidence includes
`fake-clock-boundaries-2026-07-20.md`, `atomic-crash-recovery-2026-07-20.md`,
and `follower-leader-matrix-2026-07-20.md`.

## M2 — incident replay: proved

Every named failure class in the goal maps to a permanent test in the current
suite: header authentication, content-encoding, frozen process tokens,
dual-refresh authority, missing markers, stale generations, alternate locks,
malformed writes, obsolete schedules, service PATH, legacy writer protocol,
proxy restart/dynamic registration/disconnect, and wrapper resolution. The
individual incident evidence documents and `tests/README.md` provide the
mapping.

## M3 — executable state machine: proved

`credential_state_model.py` and its state-machine/property tests cover
authority, generation, expiry, refresh, publish, failure, cooldown, relogin,
recovery, follower behavior, and generated sequences. Concurrency and atomic
replacement are exercised against the implementation. Eighteen selected
safety mutations are killed by the executable specification; see
`state-model-mutation-2026-07-20.md`.

## M4 — CI and immutable artifacts: proved

- Protected `main` requires strict `release-gate`; administrators are included,
  force pushes and deletion are disabled.
- PR CI now checks out and executes the preceding test-only `test:` commit and
  requires it to fail before accepting a production-changing head. PR 17
  proved the mechanism against its own red and green commits.
- The final gate passes 137 Python tests and four shell integration suites.
- Clean, deterministic 30-day-retained artifacts contain checksums, a manifest,
  source commit/tree, formulas, shims, deploy assets, and release tooling.

## M5 — production-shaped rollout: incomplete

Proved: isolated farol leader/vault, agent-1 follower, and UID-502 macOS
follower; private pairing; fail-closed pulls; actual environment and writer
inspection; checksum-protected artifacts; three-host verification; and repeated
rollback/restore drills. Protected runtime commit
`6acfa6681e0445f58b791b701edb216c84da7e86` is selected on all three hosts.

Missing: the dedicated account has no Claude Code credential because Anthropic
requires Pro or Max. Therefore no real leader publication, successful follower
pull/check, or credential-bearing phased rollout has occurred. Human credentials
were correctly refused as substitutes.

## M6 — continuous verification and soak: incomplete

Proved: daily hermetic CI; the fail-closed live runner; unexpected-writer
continuity; exact 30-day evidence verifier; canonical schedules; authenticated
first-failure follower alerts; and a real agent-1 failure retained in the
canonical incident pipeline.

Missing: schedules remain disabled and the macOS activation marker remains
absent. There are zero successful scheduled live-canary days, so the required
30 consecutive UTC days, final post-soak incident audit, and final restoration
drill cannot yet be proved.

## Remaining critical path

1. Explicitly authorize and fund Claude Pro or Max for the separate canary
   account, or supply an equivalent dedicated Claude Code OAuth entitlement.
2. Install only that credential, publish on farol, and pass leader plus both
   follower lifecycle runs.
3. Enable the three schedules and begin the real evidence clock.
4. After 30 complete green days, run `verify-live-soak`, audit incidents and
   writers, repeat rollback/restore, and only then mark the goal complete.
