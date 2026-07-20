# Tests

Run `tests/run fast` while developing and `tests/run full` before committing.
They currently execute the same hermetic suite; `full` is the stable release
entrypoint and will gain production-shaped tests as the goal advances.

Tests must use temporary homes, stores, ports, and fake credentials. They must
not read or mutate personal credential stores or require network access.

`test_ai_any.py` is included because `ai-any` selects and heals `ai-token`
profiles. Its automatic heal path must never override refresh authority.

`test_ai_token_refresh_rate_limit.py` enforces the refresh-throttling contract
for Claude, Kimi, and Codex: persisted `Retry-After`, no credential mutation,
one network request under concurrency, and a provider-wide host/IP cooldown.
The state-machine suite also generates cooldown and time-advance transitions.

`test_compatibility_shims.py` prevents the deprecated entrypoints from becoming
independent credential writers again, including under a stale shadowing PATH.
`test_service_environment.py` pins generated services to the invoked canonical
artifact. `test_release_artifact.py` proves clean-tree rejection, deterministic
packaging, embedded file hashes, and an external bundle checksum.
`test_release_install.py` verifies fail-closed archive validation, atomic
content-addressed selection, durable intent/completion audit records, and a
reversible rollback without touching live installation paths. It also proves
post-deploy commit convergence and detects modified, extra, or symlinked
installed payloads. `test_ci_contract.py` pins the hard release gate, daily
schedule, and 30-day artifact retention policy.

`test_ai_token_live_canary.py` proves the live runner cannot touch an ordinary
profile, start without `--live`, inherit a nested/profile-scoped home, execute
an unverified release, leak command output into evidence, or use the shared
Claude login keychain for a macOS follower. Leader and follower commands are
exercised only through fake installed releases and disposable homes.

`test_ai_token_soak_evidence.py` pins the 30-day exit gate: every required
host/role must have a successful record on every UTC day, all records must use
the expected profile and commit, and a failed duplicate can never be hidden by
a later success. Malformed, symlinked, permissively readable, or fabricated
evidence fails closed.

Every bug fix starts with a deterministic failing test and ends with that test
in this directory. A flake, retry-to-green result, or unexplained skip fails the
suite.
