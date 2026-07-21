# Strict multi-cycle TDD promotion — 2026-07-21

This supersedes the runtime pin and test count in
`completion-audit-2026-07-21-v3.md` and
`atomic-generated-state-promotion-2026-07-21.md`. Their historical findings
and evidence remain valid. No production profile, human credential, credential
value, credential hash, pairing secret, or Keychain password was used or
recorded.

## Enforcement defect and TDD proof

The pre-soak completion audit found that `tools/verify-tdd-history` stopped at
the first production commit in a pull request. One valid red test could
therefore mask any number of later unrelated production changes. It also
called a commit test-only when it changed a runnable test plus arbitrary
non-test files.

Red commit `9e7e12b` proves both bypasses deterministically in isolated Git
repositories. The old verifier accepted each invalid history, so the focused
suite failed twice. Green commit `a7b3229` scans the complete pull-request
history, accepts a red candidate only when every changed path is a runnable
test, consumes that candidate for exactly one production commit, and replays
every resulting red/production pair. The focused five-test verifier suite and
the complete 209-Python-test plus four-shell-integration gate passed. The
strengthened verifier independently replayed the preserved red commit.

## Protected release

- PR #51 release-gate runs `29842307817` and `29842309302`: passed.
- Protected-main run `29842638187`: passed.
- Merge commit: `7e3b8327fb52006b1ac3c10930efe2bba2d798a2`.
- Tree: `1bf60e7040d94a2a6fa3c59810caadd6c47bc5cd`.
- Release: `7e3b8327fb52-c174dc926afc`.
- Archive SHA-256:
  `c174dc926afcbd99ebd258f208f93c82c13d4d079a683af666313b057fd316df`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.

The protected-main artifact independently matched its external checksum, full
commit, Git tree, unchanged exact 32-file payload allowlist, every member
digest, every mode, and every source byte. Compared with the prior selected
release, the only payload member whose digest changed is
`tools/verify-tdd-history`; the credential services and lifecycle code are
byte-identical.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback to `961817df7012-cdcf26652e0e`, exact
old-release verification, restore, and final exact new-release verification.
Every host selected `7e3b8327fb52-c174dc926afc`.

After atomically changing only each mode-0600 canary configuration's expected
commit and restarting the isolated farol vault, the complete live matrix
passed:

- farol leader: `20260721T151349.419318Z-farol-leader-3383689.json`;
- agent-1 follower: `20260721T151351.554054Z-agent-1-follower-4161984.json`;
- macOS dedicated follower:
  `20260721T151354.115269Z-Kelvins-MacBook-Air-follower-51289.json`.

Each is a mode-0600 schema-3 record with a valid immediate predecessor link and
the exact role-specific successful step sequence. Atomic collection retained
all 63 records: 23 from farol, 20 from agent-1, and 20 from macOS. The daily
audit exited zero with `no completed soak day`. The isolated vault, both farol
timers, agent-1 timer, and macOS dispatcher remain healthy and enabled.
Temporary remote artifact and helper copies were removed after verification.

The clean 30-day window is pinned to `7e3b8327fb52-c174dc926afc` for July 22
through August 20 UTC. The same five real-time M6 exit items listed in
`completion-audit-2026-07-21-v3.md` remain open and become eligible on August
21 UTC.
