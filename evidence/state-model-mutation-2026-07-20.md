# Credential state-model mutation gate — 2026-07-20

The safety-critical reference model now has deterministic accepted/rejected
coverage for all 12 declared transitions in addition to 20,000 generated event
steps (100 seeds × 200 events). Expiry and `needsRelogin` recovery are explicit
transitions: an expired access credential cannot be published, recovery must
advance the generation with a fresh credential, and a follower cannot recover
canonical authority.

The expiry/recovery contract was committed red as `1e010fd`; its suite could
not import the absent `TRANSITIONS`, `access_is_fresh`, or `relogin_recovery`
symbols. The model implementation was added only after that failure.

A standard-library mutation gate creates an isolated copy of the model for
each selected fault and runs the real state-machine specification against it.
All 18 selected mutants are killed:

- accepting stale or equal-generation conflicting writes;
- assigning owner and vault handoffs to the wrong authority;
- accepting a refresh that does not advance the generation;
- losing `needsRelogin` after `invalid_grant`;
- failing to count a permitted refresh attempt;
- extending `Retry-After` beyond the one-day cap;
- allowing time to move backwards;
- publishing an expired access credential;
- leaking a canonical refresh token to a follower;
- publishing with non-follower authority;
- inventing a later follower expiry;
- mutating state after a transient failure; and
- allowing a follower to refresh;
- accepting equal-generation recovery;
- retaining `needsRelogin` after successful recovery; and
- omitting recovery from the declared transition set.

Result: 18 killed, 0 survived, for a 100% score over this explicit mutation
set. This is mutation evidence for the executable credential model, not a
claim of whole-program mutation coverage for the Bash/Python implementation.
No network, credential store, or installed executable participates.

The expanded model is included in the clean 108-Python-test release gate.
