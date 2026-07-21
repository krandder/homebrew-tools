# Complete credential-state writer promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Protected release

- PR #40 release-gate runs `29831443560` and `29831454924`: passed.
- Protected-main run `29831631221`: passed.
- Merge commit: `3da9ee56e98d47c840038f76f545e31ff054f888`.
- Tree: `9bb7b2e8e3f84988b6f4358e6c87ef62c40dcedc`.
- Release: `3da9ee56e98d-daf055d6c532`.
- Archive SHA-256:
  `daf055d6c5321a4a1dc58e4381ab4370eb75fbde1c9278e044080ba71ef83360`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.
- Gate: 186 Python tests and four shell integration suites.

The protected-main artifact was independently checked against its external
checksum, full commit, Git tree, every manifest member digest, member count,
and normalized mode set before installation.

## Final writer audit and TDD proof

The post-PR-38 inventory found that Codex publication, follower pulls, and
handoff demotion still replaced visible credential or authority state directly.
It also found unlocked in-place mutation of the vault ACL, API-token store, and
pairing store. Red commit `8ee0571` proved deterministic crash corruption and a
lost-update interleaving. Green commit `ff5ee71` introduced private mode-0600
temporary generations, fsync, atomic replacement, stale-generation cleanup,
and per-state mutation locks.

A second audit found three remaining direct client-side writers: the shared
vault configuration containing bearer-token and authority settings, Linux's
local Claude credential file, and each Codex profile's role marker. Red commit
`2455b21` proved that all three failpoints were ignored: configuration and
credentials were replaced and a Codex leader became a follower. Green commit
`7469d19` routes those writes through one per-path locked, mode-0600, fsynced,
atomic text-state writer. The complete suite and the independent TDD-history
gate passed before merge.

The resulting invariant is that every scoped credential, refresh-authority,
ACL, pairing, and API-token state writer identified by the audit either commits
a complete validated generation atomically or leaves the prior generation
intact. Concurrent read-modify-write state mutations serialize on a persistent
per-state lock.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback, exact old-release verification,
restore, and final exact new-release verification. All three selected release
`3da9ee56e98d-daf055d6c532`, commit
`3da9ee56e98d47c840038f76f545e31ff054f888`, tree
`9bb7b2e8e3f84988b6f4358e6c87ef62c40dcedc`, and the same 32-file manifest.

After atomically changing only each mode-0600 canary configuration's
`expect_commit`, the isolated leader and both followers passed their complete
manual lifecycle:

- farol leader: `20260721T125317.892033Z-farol-leader-2631868.json`;
- agent-1 follower: `20260721T125324.005558Z-agent-1-follower-4055468.json`;
- macOS dedicated follower:
  `20260721T125331.219221Z-Kelvins-MacBook-Air-follower-5801.json`.

Each schema-3 record links to its host's preceding retained evidence. The
leader recorded exact release verification then publication; each follower
recorded exact release verification, pull, then check. These manual records
prove deployment convergence but cannot count as scheduled soak coverage.

The farol two-hour timer, daily agent-1 timer, and macOS 01:20 local dispatcher
remain enabled. The macOS dispatcher retained last exit zero and its dedicated
activation marker. The daily audit exited zero with `no completed soak day`, as
required on the excluded July 21 activation day. All temporary artifact copies
were removed after verification.

The clean 30-day window is therefore pinned to
`3da9ee56e98d-daf055d6c532` for July 22 through August 20 UTC. The required
post-window scheduled anchors, final incident and writer audit, final physical
rollback/restore drill, and completion gate become eligible on August 21 UTC.
