# Private remaining-generation promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Defect and TDD proof

The post-Kimi writer audit found four remaining predictable temporary paths:
Codex remote-pull staging, Codex OAuth refresh replacement, Claude's durable
invalid-grant marker, and provider/local refresh-cooldown persistence. A stale
symlink at any fixed generation name could overwrite unrelated state before
the destination replacement.

Red commit `839f46b` proves each overwrite deterministically and rejects all
five fixed-path source forms, including the legacy Codex launcher. Green commit
`3e421dd` gives same-directory state replacements private mode-0600 generations
with fsync and atomic replacement, while network responses stage in a private
system temporary file before the existing validated locked destination copy.
The existing provider and OAuth locks remain the serialization boundary.
Build commit `418f155` pins formula version 3.1.9 to the exact implementation
commit and content digest.

## Protected release

- PR #46 release-gate runs `29836375577` and `29836379981`: passed.
- Protected-main run `29836601450`: passed.
- Merge commit: `f41bcf7bddab9c6af4cd6f277ec1b0cd8e60efc0`.
- Tree: `82f9550708ed128bff6cb6ae1212204f64abc66e`.
- Release: `f41bcf7bddab-81d3623997b5`.
- Archive SHA-256:
  `81d3623997b526b0968f950723affa865fc37976aee92db10950cf1f77453a21`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.
- Gate: 194 Python tests and four shell integration suites.

The protected-main artifact independently matched its external checksum, full
commit, Git tree, exact 32-file payload allowlist, every member digest, every
mode, and every source byte. Its `ai-token` member exactly matches
implementation commit `3e421dd309926179fde3c114b26b576a536b530b`.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each completed installation,
exact new-release verification, rollback, exact prior-release verification,
restore, and final exact new-release verification. All selected release
`f41bcf7bddab-81d3623997b5` with the commit, tree, and manifest above.

After atomically changing only each mode-0600 canary configuration's expected
commit and restarting the isolated farol vault, the complete live matrix
passed:

- farol leader: `20260721T140157.445491Z-farol-leader-3020018.json`;
- agent-1 follower: `20260721T140202.742876Z-agent-1-follower-4107808.json`;
- macOS dedicated follower:
  `20260721T140211.878059Z-Kelvins-MacBook-Air-follower-28550.json`.

Each is a mode-0600 schema-3 record with a valid predecessor link and the exact
role-specific successful step sequence. Atomic collection retained all 57
records across the three hosts. The daily audit exited zero with `no completed
soak day`.

The real 14:00 UTC farol schedule was allowed to finish before promotion and
passed on the prior release in
`20260721T140000.050509Z-farol-leader-3009712.json`. That record and the manual
promotion records are activation-day evidence only and cannot satisfy a clean
soak day. Temporary artifact and helper copies were removed after verification.

The clean 30-day window is pinned to `f41bcf7bddab-81d3623997b5` for July 22
through August 20 UTC. Post-window scheduled anchors, the final incident and
writer audit, the final physical rollback/restore drill, and the completion
gate become eligible on August 21 UTC.
