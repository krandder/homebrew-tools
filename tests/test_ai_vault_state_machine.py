import random
import unittest

from credential_state_model import (
    Authority,
    Credential,
    Rejected,
    State,
    advance_time,
    check_invariants,
    explicit_takeover,
    follower_refresh,
    invalid_grant,
    owner_sync,
    publish,
    rate_limited,
    refresh_attempt,
    refresh_success,
    transient_failure,
    vault_handoff,
)


class CredentialStateMachineTest(unittest.TestCase):
    def test_generated_event_histories_preserve_all_invariants(self):
        operations = (
            "owner", "handoff", "takeover", "refresh", "attempt", "rate-limit",
            "advance", "invalid", "transient", "publish", "follower",
        )
        for seed in range(100):
            rng = random.Random(seed)
            state = State()
            highest_generation = -1
            for _step in range(200):
                operation = rng.choice(operations)
                before = state
                blocked_attempt = operation == "attempt" and state.now < state.provider_cooldown_until
                try:
                    if operation == "owner":
                        generation = rng.randrange(20)
                        state = owner_sync(state, generation, f"owner-{generation}")
                    elif operation == "handoff":
                        generation = rng.randrange(20)
                        state = vault_handoff(state, generation, f"vault-{generation}")
                    elif operation == "takeover":
                        state = explicit_takeover(state)
                    elif operation == "refresh":
                        generation = (state.canonical.generation if state.canonical else 0) + rng.randrange(1, 4)
                        state = refresh_success(state, generation, f"rotated-{seed}-{generation}")
                    elif operation == "attempt":
                        state = refresh_attempt(state)
                    elif operation == "rate-limit":
                        state = rate_limited(state, rng.randrange(1, 301))
                    elif operation == "advance":
                        state = advance_time(state, rng.randrange(0, 301))
                    elif operation == "invalid":
                        state = invalid_grant(state)
                    elif operation == "transient":
                        state = transient_failure(state)
                    elif operation == "publish":
                        state = publish(state)
                    else:
                        state = follower_refresh(state)
                except Rejected:
                    state = before

                check_invariants(state)
                if blocked_attempt:
                    self.assertEqual(state.refresh_requests, before.refresh_requests)
                if state.canonical is not None:
                    self.assertGreaterEqual(state.canonical.generation, highest_generation)
                    highest_generation = state.canonical.generation

    def test_invariant_checker_detects_a_refresh_token_leak(self):
        broken = State(
            canonical=Credential(1, "canonical-refresh", Authority.VAULT),
            follower=Credential(1, "leaked-refresh", Authority.FOLLOWER),
        )
        with self.assertRaisesRegex(AssertionError, "functional refresh token"):
            check_invariants(broken)

    def test_provider_cooldown_blocks_every_profile_until_retry_after(self):
        state = vault_handoff(State(), 1, "real-refresh")
        state = refresh_attempt(state)
        canonical = state.canonical
        state = rate_limited(state, 120)

        with self.assertRaisesRegex(Rejected, "cooldown"):
            refresh_attempt(state)
        self.assertEqual(state.refresh_requests, 1)
        self.assertEqual(state.canonical, canonical)

        state = advance_time(state, 119)
        with self.assertRaisesRegex(Rejected, "cooldown"):
            refresh_attempt(state)
        state = advance_time(state, 1)
        state = refresh_attempt(state)
        self.assertEqual(state.refresh_requests, 2)


if __name__ == "__main__":
    unittest.main()
