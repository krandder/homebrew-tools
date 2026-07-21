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

`test_ai_token_canary_deployment.py` keeps the physical scheduler boundary in
the same immutable release as the runner. It pins the farol and agent-1 units,
daily UTC cadence, Mac login-session dispatcher, exact UID switch, activation
marker, and dedicated Keychain unlock path. Passwords and host credentials are
deployment state and never enter the artifact.

`test_ai_token_canary_alerts.py` proves follower failures cross an authenticated,
sanitized vault route into the incident pipeline, while human profiles and
credential-bearing evidence fields cannot enter that path.

`test_tdd_history.py` proves a production-changing pull request cannot pass the
release gate unless an earlier `test:` commit changed only runnable tests and
the complete suite actually failed at that commit.

`test_ai_token_soak_evidence.py` pins the 30-day exit gate: every required
host/role must have a scheduler-marked successful record on every UTC day, all
records must use one expected profile, commit, and immutable release artifact
ID, and a failed duplicate can never be hidden by a later success. A
post-window scheduled anchor closes each retained chain. Malformed, symlinked,
permissively readable, omitted, or fabricated evidence fails closed.

Canary evidence schema 3 carries scheduler provenance, a SHA-256 link to the
previous sanitized evidence record, and credential-store metadata before and
after each run. `test_ai_token_live_canary.py` proves an expected canary
mutation chains cleanly, while a between-run writer or permissive credential
file stops before release execution. `test_ai_token_soak_evidence.py`
independently rechecks the same continuity across the retained host histories.
On macOS this is the dedicated Keychain item's account and creation/modification
timestamps; the password is never requested. No credential bytes or credential
hashes enter evidence.

`test_ai_token_soak_collection.py` proves the operator collector creates its
three-host output atomically and copies every regular mode-0600 JSON record with
a source/digest manifest. Path traversal, nested files, symlinks, AppleDouble
metadata, permissive modes, duplicate filenames, invalid/non-JSON members, and
an existing destination all fail without leaving partial output.

Every bug fix starts with a deterministic failing test and ends with that test
in this directory. A flake, retry-to-green result, or unexplained skip fails the
suite.
