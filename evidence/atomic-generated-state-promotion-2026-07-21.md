# Atomic generated-state promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Defects and TDD proof

The final completion and writer audit found three remaining classes of unsafe
generated state. Generated wrappers, follower configuration, shell startup
edits, systemd units, and launchd plists could follow a destination symlink or
lose the previous working entrypoint if generation crashed. Event and audit
logs, `authorized_keys`, deployment records, and release checksum output could
follow a planted symlink. The HTTP heartbeat and debug snapshots still used a
direct truncating writer.

The protected history retains each deterministic failure before its fix:

- red `71c7db5` and green `c1c51d4` cover every generated entrypoint, a
  dangling follower-config symlink, and crash continuity;
- reds `59dd85a` and `fc8e379` plus green `5fc1b83` cover the append-only,
  authorization, deployment, and release writers; and
- red `798d2d3` and green `371ddda` cover authenticated HTTP heartbeat state
  end to end and reject the direct writer statically.

The green paths use private same-directory generations, locks, fsync, atomic
replacement, no-follow append descriptors, and complete-write loops as
appropriate. Formula commits `1b0f5b4` and `65a547a` pin the exact hardened
component sources. `verify-tdd-history` accepted the red-before-green history.

## Protected release

- PR #48 release-gate runs `29839426884` and `29839438281`: passed.
- Protected-main run `29839659857`: passed.
- Merge commit: `961817df7012a82fa6ff956ed60f77c542c21c57`.
- Tree: `521e60cd520982d33ca66f2a9e3e0b2cfbd005b3`.
- Release: `961817df7012-cdcf26652e0e`.
- Archive SHA-256:
  `cdcf26652e0ee60fabc18ccbbb239b307bad763edd3b2a4c861b1d3556244d89`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.
- Gate: 205 Python tests and four shell integration suites.

The protected-main artifact independently matched its external checksum, full
commit, Git tree, unchanged exact 32-file payload allowlist, every member
digest, every mode, and every source byte. Its `ai-token` and `ai-vault`
members exactly match implementation commit
`5fc1b831e0835ff194d0de0a1e5cacdb64b429dd`; `ai-vault-http` exactly matches
`371ddda3fcc26930c58910208929fc5ab94a6979`.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback, exact prior-release verification,
restore, and final exact new-release verification. Every host selected release
`961817df7012-cdcf26652e0e` with the commit, tree, and manifest above; the
verified rollback target was `f41bcf7bddab-81d3623997b5`.

After atomically changing only each mode-0600 canary configuration's expected
commit and restarting the isolated farol vault, the complete live matrix
passed:

- farol leader: `20260721T143936.571535Z-farol-leader-3216583.json`;
- agent-1 follower: `20260721T143942.701578Z-agent-1-follower-4136255.json`;
- macOS dedicated follower:
  `20260721T143949.397032Z-Kelvins-MacBook-Air-follower-40494.json`.

Each is a mode-0600 schema-3 record with a valid immediate predecessor link and
the exact role-specific successful step sequence. Atomic collection retained
all 60 records: 22 from farol, 19 from agent-1, and 19 from macOS. The daily
audit exited zero with `no completed soak day`, as required before July 22 is
complete.

Both farol timers, the isolated vault, and the agent-1 timer remain enabled and
active. The macOS dispatcher remains loaded; its canary-owned activation marker
is mode 0600 and its last exit is zero. Temporary remote artifact and helper
copies were removed after verification.

The clean 30-day window is pinned to `961817df7012-cdcf26652e0e` for July 22
through August 20 UTC. Post-window scheduled anchors, the final incident and
writer audit, the final physical rollback/restore drill, and the completion
gate become eligible on August 21 UTC.
