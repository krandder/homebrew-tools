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

Every bug fix starts with a deterministic failing test and ends with that test
in this directory. A flake, retry-to-green result, or unexplained skip fails the
suite.
