# Immutable red-proof promotion — 2026-07-21

This supersedes the runtime pin and test count in
`strict-multi-cycle-tdd-promotion-2026-07-21.md`. Its multi-cycle finding and
historical evidence remain valid. No production profile, human credential,
credential value, credential hash, pairing secret, or Keychain password was
used or recorded.

## Enforcement defects and TDD proof

The follow-up audit found two remaining ways to make red evidence lie. A green
production commit could rewrite or weaken the runnable test that supplied its
red proof. A merge resolution could introduce production changes because the
verifier excluded merge commits from its history scan.

Red commit `43c7230` builds both invalid histories in isolated repositories;
the prior verifier accepted each, so the focused suite failed twice. Green
commit `3b0f788` rejects any production commit that also changes runnable tests
and rejects every merge commit in the pull-request range. The red test is
therefore immutable through its paired green production commit, and production
cannot hide in merge resolution. The focused seven-test suite, the complete
211-Python-test plus four-shell-integration gate, and independent red replay
all passed.

## Protected release

- PR #53 release-gate runs `29843928763` and `29843929211`: passed.
- Protected-main run `29844206916`: passed.
- Merge commit: `0f235c2aecce82ea5dd7761f3d9b7707a0157230`.
- Tree: `1697c77152907e40ac20fb718a66f5aced989382`.
- Release: `0f235c2aecce-e2ce134f3805`.
- Archive SHA-256:
  `e2ce134f38052a7db4903c57df9d740e81d1af3fa9d5161e0d7ab65bd60de636`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.

The protected-main artifact independently matched its external checksum, full
commit, Git tree, unchanged exact allowlist, every digest, every mode, and
every source byte. Compared with the prior selected release, the only changed
payload member is `tools/verify-tdd-history`; all credential and lifecycle
bytes are identical.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback to `7e3b8327fb52-c174dc926afc`, exact
old-release verification, restore, and final exact new-release verification.
After atomically updating only each mode-0600 expected-commit pin and restarting
the isolated vault, the complete live matrix passed:

- farol leader: `20260721T153339.124068Z-farol-leader-3490674.json`;
- agent-1 follower: `20260721T153341.259188Z-agent-1-follower-4177268.json`;
- macOS dedicated follower:
  `20260721T153343.772298Z-Kelvins-MacBook-Air-follower-57385.json`.

Each is a mode-0600 schema-3 record with the exact role-specific successful
steps and a verified immediate predecessor. Atomic collection retained all 66
records: 24 from farol, 21 from agent-1, and 21 from macOS. The daily audit
exited zero with `no completed soak day`; all schedules remained enabled.
Temporary remote artifact and helper copies were removed after verification.

The clean 30-day window is pinned to `0f235c2aecce-e2ce134f3805` for July 22
through August 20 UTC. The five real-time M6 exit items remain open for August
21 UTC.
