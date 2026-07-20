import random
import unittest

from credential_state_model import (
    Authority,
    Credential,
    Rejected,
    State,
    TRANSITIONS,
    access_is_fresh,
    advance_time,
    check_invariants,
    explicit_takeover,
    follower_refresh,
    invalid_grant,
    owner_sync,
    publish,
    rate_limited,
    relogin_recovery,
    refresh_attempt,
    refresh_success,
    transient_failure,
    vault_handoff,
)


class CredentialStateMachineTest(unittest.TestCase):
    def test_authority_generation_and_failure_transition_contract(self):
        state = owner_sync(State(), 2, "owner-refresh")
        self.assertEqual(state.canonical.authority, Authority.OWNER)
        with self.assertRaisesRegex(Rejected, "stale"):
            owner_sync(state, 1, "older-refresh")
        with self.assertRaisesRegex(Rejected, "conflicting"):
            owner_sync(state, 2, "different-refresh")

        state = vault_handoff(state, 3, "vault-refresh")
        self.assertEqual(state.canonical.authority, Authority.VAULT)
        with self.assertRaisesRegex(Rejected, "advance"):
            refresh_success(state, 3, "same-generation")
        state = refresh_success(state, 4, "rotated-refresh")
        self.assertEqual(state.canonical.generation, 4)

        published = publish(state)
        self.assertEqual(published.follower.authority, Authority.FOLLOWER)
        self.assertIsNone(published.follower.refresh_token)
        with self.assertRaisesRegex(Rejected, "never refresh"):
            follower_refresh(published)

        unchanged = transient_failure(published)
        self.assertEqual(unchanged, published)
        relogin = invalid_grant(state)
        self.assertTrue(relogin.canonical.needs_relogin)
        with self.assertRaisesRegex(Rejected, "relogin"):
            refresh_attempt(relogin)

    def test_time_and_retry_after_boundaries(self):
        with self.assertRaisesRegex(Rejected, "backwards"):
            advance_time(State(), -1)
        with self.assertRaisesRegex(Rejected, "retry-after"):
            rate_limited(State(), 0)
        state = rate_limited(State(now=10), 100_000)
        self.assertEqual(state.provider_cooldown_until, 86_410)
        self.assertEqual(advance_time(state, 0), state)

    def test_explicit_takeover_is_required_before_owner_chain_refresh(self):
        owner = owner_sync(State(), 1, "owner-refresh")
        with self.assertRaisesRegex(Rejected, "outside vault authority"):
            refresh_attempt(owner)
        vault = explicit_takeover(owner)
        self.assertEqual(vault.canonical.authority, Authority.VAULT)
        attempted = refresh_attempt(vault)
        self.assertEqual(attempted.refresh_requests, 1)

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

    def test_expiry_and_relogin_recovery_transitions(self):
        state = vault_handoff(
            State(now=100), 1, "vault-refresh", expires_at=160,
        )
        self.assertFalse(access_is_fresh(state, state.canonical))
        with self.assertRaisesRegex(Rejected, "expired"):
            publish(state)

        marked = invalid_grant(state)
        with self.assertRaisesRegex(Rejected, "advance"):
            relogin_recovery(
                marked, 1, "same-generation", Authority.OWNER, expires_at=1000,
            )
        recovered = relogin_recovery(
            marked, 2, "fresh-owner-refresh", Authority.OWNER, expires_at=1000,
        )
        self.assertFalse(recovered.canonical.needs_relogin)
        self.assertEqual(recovered.canonical.authority, Authority.OWNER)
        self.assertTrue(access_is_fresh(recovered, recovered.canonical))
        self.assertEqual(publish(recovered).follower.expires_at, 1000)

    def test_every_declared_transition_has_accepted_and_rejected_coverage(self):
        observed = set()

        def exercise(name, function):
            try:
                function()
                observed.add((name, "accepted"))
            except Rejected:
                observed.add((name, "rejected"))

        empty = State(now=100)
        owner = owner_sync(empty, 1, "owner-refresh", expires_at=1000)
        vault = vault_handoff(empty, 1, "vault-refresh", expires_at=1000)
        marked = invalid_grant(vault)
        expired = vault_handoff(empty, 1, "vault-refresh", expires_at=160)
        cooled = rate_limited(vault, 120)
        cases = {
            "owner-sync": (
                lambda: owner_sync(empty, 1, "owner-refresh"),
                lambda: owner_sync(owner, 0, "stale-refresh"),
            ),
            "vault-handoff": (
                lambda: vault_handoff(empty, 1, "vault-refresh"),
                lambda: vault_handoff(vault, 1, "conflict"),
            ),
            "takeover": (lambda: explicit_takeover(owner), lambda: explicit_takeover(empty)),
            "refresh-success": (
                lambda: refresh_success(vault, 2, "rotated"),
                lambda: refresh_success(owner, 2, "rotated"),
            ),
            "invalid-grant": (lambda: invalid_grant(vault), lambda: invalid_grant(owner)),
            "transient-failure": (lambda: transient_failure(vault),),
            "refresh-attempt": (lambda: refresh_attempt(vault), lambda: refresh_attempt(cooled)),
            "rate-limit": (lambda: rate_limited(vault, 1), lambda: rate_limited(vault, 0)),
            "advance-time": (lambda: advance_time(vault, 1), lambda: advance_time(vault, -1)),
            "publish": (lambda: publish(vault), lambda: publish(expired)),
            "follower-refresh": (lambda: follower_refresh(vault),),
            "relogin-recovery": (
                lambda: relogin_recovery(marked, 2, "recovered", Authority.OWNER),
                lambda: relogin_recovery(vault, 2, "not-marked", Authority.OWNER),
            ),
        }
        self.assertEqual(set(cases), set(TRANSITIONS))
        for name, functions in cases.items():
            for function in functions:
                exercise(name, function)

        expected = {
            (name, outcome)
            for name in TRANSITIONS
            for outcome in ({"rejected"} if name == "follower-refresh" else
                            {"accepted"} if name == "transient-failure" else
                            {"accepted", "rejected"})
        }
        self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
