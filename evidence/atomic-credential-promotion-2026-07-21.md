# Atomic credential and formula promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Protected release

- PR #38 release-gate runs `29804934067` and `29804944894`: passed.
- Protected-main run `29805065717`: passed.
- Merge commit: `5185f09529611695d2cbed52e9bd7c532765cfa4`.
- Tree: `d45ef0040c9caaec1e371ce1f885d9a0e34f9d8c`.
- Release: `5185f0952961-e72c82006740`.
- Archive SHA-256:
  `e72c82006740c2d61474152e5fba2acab249bf633ab3442c0971442314690cbb`.
- Manifest: 32 verified regular files, all normalized to mode 0644 or 0755.
- Gate: 178 Python tests and four shell integration suites.

The artifact was downloaded from the protected-main workflow. Its external
checksum, full commit, tree, every member digest, member count, and normalized
mode set were independently verified before installation.

## TDD defects closed

The requirement-by-requirement Kimi replay audit found three real gaps:

1. Claude canonical and shared publication still truncated visible JSON in
   place. Red `9865fd5` proved deterministic pre-replace crashes could pass
   through; green `cb9c1e9` writes and fsyncs private mode-0600 generations,
   atomically replaces them, retains valid prior JSON on failure, removes
   abandoned generations on retry, and never logs a failed replacement as a
   successful refresh.
2. Formula checksum tests ignored the bytes downloaded by the formula URL.
   Red `b1f94be` exposed an old `ai-token` source pin plus four moving `main`
   URLs; green `e813843` pins all five scoped formula sources to a reachable
   canonical commit and checks URL bytes, checksum, and current source agree.
3. Release archives inherited group-write bits that Git does not track. Red
   `20f1fd3` produced two artifacts from otherwise identical clean sources;
   green `00aee32` normalizes release members from the tracked executable bit.

`tools/verify-tdd-history` independently replayed the first red commit against
the complete suite before accepting the production change. The authority
boundary suite was also reinforced with missing and deliberately inverted
Claude/Kimi authority markers.

## Three-host promotion

Farol, agent-1, and the dedicated macOS UID 502 each performed install, exact
new-release verification, rollback, exact old-release verification, restore,
and final exact new-release verification. All selected the same commit, tree,
32-file manifest, and release ID.

The first farol manual invocation failed closed at release verification because
its canary config still expected the previous commit. It made no provider call,
retained sanitized schema-3 evidence, and was not hidden. Updating only the
mode-0600 `expect_commit` field produced the successful linked leader record
`20260721T055228.022170Z-farol-leader-529195.json`.

Agent-1 passed follower pull/check in
`20260721T055304.404502Z-agent-1-follower-3737373.json`. The dedicated macOS
UID/keychain path passed in
`20260721T122207.291042Z-Kelvins-MacBook-Air-follower-95394.json`. All three are
manual schema-3 records and therefore cannot satisfy a scheduled soak day.

Farol then passed scheduler-native leader records on the new release at 06:00,
08:00, 10:00, and 12:00 UTC. Atomic collection retained all 44 records: 16
farol, 14 agent-1, and 14 macOS. The independent daily auditor again exited
zero with `no completed soak day`, as required before July 22 is complete. No
canary incident was added to the canonical July 21 incident store during the
promotion.

All staging archives, checksums, and the temporary collection were removed
from farol, agent-1, and the Mac after verification. July 21 remains an
excluded activation day. The clean window is July 22 through August 20 UTC on
release `5185f0952961-e72c82006740`; the final post-window anchors and gate are
eligible on August 21 UTC.
