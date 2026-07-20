import pathlib
import subprocess
import sys
import tempfile
import unittest


TESTS = pathlib.Path(__file__).resolve().parent
MODEL = TESTS / "credential_state_model.py"
SPEC = TESTS / "test_ai_vault_state_machine.py"


class StateModelMutationTest(unittest.TestCase):
    def test_selected_safety_mutations_are_all_killed(self):
        mutations = {
            "accept-stale": (
                "if generation < current.generation:",
                "if generation > current.generation:",
            ),
            "accept-conflict": (
                "if generation == current.generation and refresh_token != current.refresh_token:",
                "if generation < current.generation and refresh_token != current.refresh_token:",
            ),
            "owner-becomes-vault": (
                "Credential(generation, refresh_token, Authority.OWNER)",
                "Credential(generation, refresh_token, Authority.VAULT)",
            ),
            "handoff-stays-owner": (
                "return replace(state, canonical=Credential(generation, refresh_token, Authority.VAULT))",
                "return replace(state, canonical=Credential(generation, refresh_token, Authority.OWNER))",
            ),
            "equal-generation-refresh": (
                "if generation <= current.generation:",
                "if generation < current.generation:",
            ),
            "lose-relogin-marker": ("needs_relogin=True", "needs_relogin=False"),
            "lose-refresh-accounting": (
                "refresh_requests=state.refresh_requests + 1",
                "refresh_requests=state.refresh_requests + 0",
            ),
            "extend-cooldown-beyond-cap": (
                "min(retry_after, 86400)",
                "max(retry_after, 86400)",
            ),
            "allow-backwards-time": ("if seconds < 0:", "if seconds < -1:"),
            "leak-follower-refresh": (
                "Credential(current.generation, None, Authority.FOLLOWER, current.needs_relogin)",
                "Credential(current.generation, current.refresh_token, Authority.FOLLOWER, current.needs_relogin)",
            ),
            "wrong-follower-authority": (
                "Credential(current.generation, None, Authority.FOLLOWER, current.needs_relogin)",
                "Credential(current.generation, None, Authority.VAULT, current.needs_relogin)",
            ),
            "mutate-on-transient": (
                "def transient_failure(state):\n    return state",
                "def transient_failure(state):\n    return replace(state, refresh_requests=state.refresh_requests + 1)",
            ),
            "allow-follower-refresh": (
                'def follower_refresh(state):\n    raise Rejected("followers never refresh")',
                "def follower_refresh(state):\n    return state",
            ),
        }
        source = MODEL.read_text()
        for name, (original, mutant) in mutations.items():
            with self.subTest(mutation=name), tempfile.TemporaryDirectory() as directory:
                self.assertIn(original, source)
                root = pathlib.Path(directory)
                (root / MODEL.name).write_text(source.replace(original, mutant, 1))
                (root / SPEC.name).write_text(SPEC.read_text())
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", SPEC.stem],
                    cwd=root,
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                self.assertNotEqual(
                    result.returncode,
                    0,
                    f"mutation survived: {name}\n{result.stdout}\n{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
