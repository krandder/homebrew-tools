# Tests

Run `tests/run fast` while developing and `tests/run full` before committing.
They currently execute the same hermetic suite; `full` is the stable release
entrypoint and will gain production-shaped tests as the goal advances.

Tests must use temporary homes, stores, ports, and fake credentials. They must
not read or mutate personal credential stores or require network access.

Every bug fix starts with a deterministic failing test and ends with that test
in this directory. A flake, retry-to-green result, or unexplained skip fails the
suite.
