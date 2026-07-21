# macOS Keychain continuity — 2026-07-21

No credential password, token, credential hash, or human Keychain participated
in the tests. Generated `security` metadata output was supplied to the runner
under mocks.

## Defect

The dedicated macOS canary stores Claude credentials in its isolated Keychain,
but schema-3 evidence still snapshotted
`~/.claude/.credentials.json`. That file does not exist on macOS, so every
record said `exists: false` and an unexpected Keychain writer was invisible.

## Red and green

Commit `d284b33` first required the runner to inspect the real Keychain item
without a password-bearing command, narrowly migrate the old false file
snapshot, and make Keychain metadata valid in the soak verifier. The old code
had neither Keychain snapshot nor migration function, and the verifier rejected
the new safe metadata shape.

Commit `2a5f18f` invokes `/usr/bin/security find-generic-password` without
`-w` or `-g`, discards stderr, and retains only the validated dedicated account
plus creation and modification timestamps. Missing items are represented
without contents. Exactly one legacy `local: exists false` to dedicated
Keychain transition is allowed; subsequent metadata drift fails before release
verification. The targeted 28-test gate and complete fast suite passed without
retry.
