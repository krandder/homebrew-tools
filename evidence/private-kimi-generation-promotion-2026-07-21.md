# Private Kimi generation promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Defect and TDD proof

The final follower-concurrency pass found that Kimi pull, publish, handoff, and
refresh used predictable shared `.tmp` paths. Red commit `c3323cd` demonstrates
the consequence: follower pull follows a stale `kimi-code.json.tmp` symlink,
overwrites unrelated state, and replaces the credential file with that
symlink. It also blocks every remaining predictable Kimi credential writer.

Green commit `30e0024` routes pull, publish, and handoff through one
per-destination locked writer using private mode-0600 generations, fsync, and
atomic replacement. Provider refresh retains its provider-wide lock and now
uses a private generation. The Kimi freshness, rate-limit concurrency,
HTTP/SSH follower-leader, revocation, and launcher matrices passed before the
complete gate.

## Protected release

- PR #44 release-gate runs `29834686917` and `29834691736`: passed.
- Protected-main run `29834904652`: passed.
- Merge commit: `21e16f96c654bd768c99053f7fd1be4fadd98f91`.
- Tree: `55a2a3c994224875a5e67d6c35259176165943a9`.
- Release: `21e16f96c654-d4de30c4a5f1`.
- Archive SHA-256:
  `d4de30c4a5f12aa1311b16efc45a3eb312972ec0bd1568fa39aa65a21eb94d90`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.
- Gate: 189 Python tests and four shell integration suites.

The protected-main artifact independently matched its external checksum, full
commit, Git tree, every member digest, member count, and normalized mode set.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback, exact prior-release verification,
restore, and final exact new-release verification. All selected release
`21e16f96c654-d4de30c4a5f1` with the commit, tree, and manifest above.

The isolated live matrix then passed:

- farol leader: `20260721T133616.948031Z-farol-leader-2877709.json`;
- agent-1 follower: `20260721T133627.789600Z-agent-1-follower-4088272.json`;
- macOS dedicated follower:
  `20260721T133629.449030Z-Kelvins-MacBook-Air-follower-19319.json`.

Each record is mode-0600 schema-3 evidence linked to its host's preceding
record. Manual activation-day runs cannot satisfy scheduled soak coverage.
Temporary artifact copies were removed after verification.

The clean 30-day window is pinned to `21e16f96c654-d4de30c4a5f1` for July 22
through August 20 UTC. Post-window scheduled anchors, the final incident and
writer audit, the final physical rollback/restore drill, and the completion
gate become eligible on August 21 UTC.
