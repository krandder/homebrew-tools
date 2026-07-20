# Canonical canary scheduler assets — 2026-07-20

The completion audit found that the live runners were installed from immutable
artifacts, but their systemd/launchd definitions and macOS UID/Keychain wrappers
had been copied from temporary deployment files. That left a configuration
boundary outside the canonical release.

## Red

Commit `107e807` added three contracts before any production asset existed:

- every farol, agent-1, and macOS scheduler file must exist and be included in
  `tools/build-release`;
- Linux units must execute the content-addressed `current` runner with the
  isolated config and declared daily UTC cadence; and
- macOS must dispatch through the exact dedicated UID, require an activation
  marker, and unlock only the custom canary Keychain.

The targeted suite failed with three missing-file errors and one missing
payload failure. This was the expected historical defect.

## Green

Commit `92ade3e` adds the nine deployed scheduler assets under
`deploy/canary/` and includes them in the immutable manifest. The Mac password
remains external mode-0600 deployment state; the release contains only its path
and never a secret. The targeted scheduler and release-artifact suites passed
five tests.

The complete clean-tree gate then passed 130 Python tests and four shell
integration suites. No live service, timer, credential, or selected release was
changed by this red/green cycle. Physical promotion must use the protected CI
artifact after merge, followed by the same verify/rollback/restore drill.
