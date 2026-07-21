# Complete scoped-interface promotion — 2026-07-21

This supersedes the runtime pin and test count in
`complete-test-integrity-promotion-2026-07-21.md`; its PR #56/#57 findings and
historical evidence remain valid. No production profile, human credential,
credential value, credential hash, pairing secret, or Keychain password was
used or recorded.

## Final allowlist defect and red proof

The complete scoped-file audit found that `ai-any`, the remaining provider
wrappers, all three mirrors, and all three proxies were tested but absent from
the immutable release and, except for one accidental filename-prefix match,
were not classified as production by the red-history verifier. `ai-any` also
had mode 0644 in Git even though it is a command entrypoint.

PR #59 preserves the release omissions, TDD-classification omissions, and mode
failure in red commit `9d11ecf`. Green commit `1b2d7f9` governs and packages all
ten scoped healing interfaces and gives `ai-any` mode 0755. The formula test
also verifies every wrapper, mirror, and proxy resource URL, canonical commit,
checksum, and current source byte. Branch/PR runs `29851166091` and
`29851167785`, plus protected-main run `29851486177`, passed 220 Python tests
and four shell integration suites with zero accepted skips or expected
failures.

## Protected release

- Merge commit: `6201b1920093cc605c7e04840c967407ae24d644`.
- Tree: `7a1614d9b39bdf7a524aee753a430cb9065459bb`.
- Release: `6201b1920093-f8bd4e418821`.
- Archive SHA-256:
  `f8bd4e418821d5cf6cd6c17e15e027da7b3e5ac0747549d52448795086bc5641`.
- Manifest: 42 verified regular files with normalized 0644/0755 modes;
  `ai-any` is 0755.

The protected-main artifact independently matched its external checksum,
commit, tree, member digests, and modes. Relative to the prior deployed
release, the only changes are the nine newly included interface members plus
`tools/build-release` and `tools/verify-tdd-history`; all credential, vault,
lifecycle, canary, scheduler, and deployment-unit bytes are identical.

## Three-host reversible promotion

Farol, agent-1, and dedicated macOS UID 502 each installed and verified the
new 42-file release, rolled back to `ed994de4434e-5179f403c404`, verified the
old 33-file release, restored, and verified the new release again. Each
mode-0600 config atomically changed only `expect_commit`; the isolated Farol
user vault restarted active.

The authority-ordered manual live matrix passed:

- Farol leader:
  `20260721T170921.843883Z-farol-leader-4021501.json`;
- agent-1 follower:
  `20260721T170930.643290Z-agent-1-follower-55209.json`;
- macOS dedicated follower:
  `20260721T170933.095200Z-Kelvins-MacBook-Air-follower-86665.json`.

Each record is mode-0600 schema 3 on `canary-claude` and the exact commit and
release, has the exact role-specific successful steps, and verifies its
immediate predecessor filename/hash. Atomic collection retained 73 records:
27 from Farol, 23 from agent-1, and 23 from macOS. Sanitized telemetry after
promotion contained zero canary 429/rate-limit/cooldown events. The cumulative
auditor correctly returned `no completed soak day`.

All public remote staging files and the temporary atomic config helper were
removed. Farol's two-hour timer, daily audit timer, and isolated vault remain
enabled and active; the existing agent-1 and macOS schedules were unchanged.
The clean 30-day window is pinned to `6201b1920093-f8bd4e418821` for July 22
through August 20 UTC. The required pre-window unattended Farol leader run was
subsequently satisfied and is recorded in
`final-scoped-pin-unattended-leader-2026-07-21.md`; post-window anchors, final
audits, and the final physical rollback/restore remain due August 21 UTC.
