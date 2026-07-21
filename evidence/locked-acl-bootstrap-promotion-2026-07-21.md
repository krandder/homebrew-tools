# Locked ACL bootstrap promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Defect and TDD proof

The final static writer pass found that a missing `acl.json` was created before
`ai-vault` acquired `acl.json.lock`. A concurrent first-start process could
therefore recreate the default ACL over an enrollment committed by another
process.

Red commit `c36ce39` holds the real ACL lock, starts enrollment against a
missing ACL, and proves the old implementation exposes the new ACL while the
lock is still held. Green commit `85fd87a` routes first initialization through
the existing locked, mode-0600, fsynced atomic state mutator. The test then
proves that no ACL exists before lock acquisition and that initialization plus
enrollment completes without state loss after release.

## Protected release

- PR #42 release-gate runs `29833078101` and `29833082710`: passed.
- Protected-main run `29833308631`: passed.
- Merge commit: `9ccdf7408f6b555bd76c02d3e5dd653b0ec2db12`.
- Tree: `e214c4a85b8a8338c84eb1848bb7cb76258dcb9d`.
- Release: `9ccdf7408f6b-ed61d7a9cf29`.
- Archive SHA-256:
  `ed61d7a9cf29e0bbed1277b684c7ac5173a3fc691ae99c81e596dc3cd480b36e`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.
- Gate: 187 Python tests and four shell integration suites.

The protected-main artifact independently matched its external checksum, full
commit, Git tree, every manifest member digest, member count, and normalized
mode set before installation.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback, exact prior-release verification,
restore, and final exact new-release verification. All selected release
`9ccdf7408f6b-ed61d7a9cf29` with the commit, tree, and 32-file manifest above.

The isolated live matrix then passed and linked to each host's preceding
retained evidence:

- farol leader: `20260721T131444.236316Z-farol-leader-2748432.json`;
- agent-1 follower: `20260721T131451.458939Z-agent-1-follower-4071492.json`;
- macOS dedicated follower:
  `20260721T131453.560376Z-Kelvins-MacBook-Air-follower-12470.json`.

The leader recorded exact release verification then publication. Each
follower recorded exact release verification, pull, then check. These are
manual activation-day records and cannot satisfy scheduled soak coverage.

The two-hour farol timer, daily agent-1 timer, and macOS 01:20 local dispatcher
remain enabled. The daily audit exited zero with `no completed soak day`, as
required before July 22 is complete. Temporary artifact copies were removed
after verification.

The clean 30-day window is pinned to `9ccdf7408f6b-ed61d7a9cf29` for July 22
through August 20 UTC. Post-window scheduled anchors, the final incident and
writer audit, the final physical rollback/restore drill, and the completion
gate become eligible on August 21 UTC.
