# Credential state-model mutation gate — 2026-07-20

The safety-critical reference model now has deterministic transition tests in
addition to 20,000 generated event steps (100 seeds × 200 events).

A standard-library mutation gate creates an isolated copy of the model for
each selected fault and runs the real state-machine specification against it.
All 13 selected mutants are killed:

- accepting stale or equal-generation conflicting writes;
- assigning owner and vault handoffs to the wrong authority;
- accepting a refresh that does not advance the generation;
- losing `needsRelogin` after `invalid_grant`;
- failing to count a permitted refresh attempt;
- extending `Retry-After` beyond the one-day cap;
- allowing time to move backwards;
- leaking a canonical refresh token to a follower;
- publishing with non-follower authority;
- mutating state after a transient failure; and
- allowing a follower to refresh.

Result: 13 killed, 0 survived, for a 100% score over this explicit mutation
set. This is mutation evidence for the executable credential model, not a
claim of whole-program mutation coverage for the Bash/Python implementation.
No network, credential store, or installed executable participates.
