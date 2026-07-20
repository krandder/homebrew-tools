# Mechanically enforced red-before-green history — 2026-07-20

The completion audit found that the release workflow ran the final green suite
but did not independently prove the required earlier red state. PR descriptions
and evidence documents could describe red/green discipline, yet branch
protection had no executable check for it.

## Red

Commit `ee9ee375e469d85a6e6809e469dcb379711ebcf4` added contracts for three cases:

- accept a runnable `test:` commit whose suite fails before the implementation;
- reject production and tests committed together; and
- reject a purported red commit whose suite still passes.

The focused run failed because `tools/verify-tdd-history` did not exist and the
workflow had neither full history nor a red-history step.

## Green

Commit `6109f8e04eebb1af6084eb7005386f30d35ad068` adds the standard-library-only
verifier and makes it a required step of the existing protected
`release-gate` on pull requests. Checkout now fetches complete history. Before
the final artifact build, the verifier requires a preceding test-only `test:`
commit, creates a detached worktree at that commit, and requires the complete
suite to return nonzero. Production and tests introduced together cannot pass.

The full repository gate passed 137 Python tests and four shell integration
suites. The verifier then checked its own real branch history and reported:

`verified red-before-green (ee9ee375... -> 6109f8e...)`

Push, scheduled, and manual builds still run the final clean artifact gate.
Protected `main` requires the pull-request release gate, so the normal merge
path cannot bypass the red proof.
