import fcntl
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_VAULT = ROOT / "ai-vault"


class VaultStateWriteTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.temporary.name)
        self.vault = self.home / "vault"
        self.vault.mkdir()
        self.acl = self.vault / "acl.json"
        self.acl.write_text(json.dumps({
            "operator": "admin",
            "admins": ["admin"],
            "profiles": {
                "claude:fixture": {
                    "owner": "owner",
                    "pullers": ["owner"],
                    "kind": "claude",
                },
            },
        }))
        self.acl.chmod(0o600)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CODEX_VAULT_DIR": str(self.vault),
            "CODEX_VAULT_USER": "admin",
            "CODEX_PROFILES_DIR": str(self.home / "codex-profiles"),
            "CLAUDE_PROFILES_DIR": str(self.home / "claude-profiles"),
            "CODEX_SHARED_DIR": str(self.home / "codex-shared"),
            "CLAUDE_SHARED_DIR": str(self.home / "claude-shared"),
            "PATH": "/usr/bin:/bin",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def run_vault(self, *arguments, **environment):
        return subprocess.run(
            [AI_VAULT, *arguments],
            env={**self.env, **environment},
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_crash_before_state_replace_preserves_valid_acl(self):
        before = self.acl.read_bytes()
        result = self.run_vault(
            "enroll", "codex", "new-profile", "new-owner",
            AI_VAULT_TEST_STATE_CRASH_AT="before-replace",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.acl.read_bytes(), before)
        json.loads(self.acl.read_text())

    def test_concurrent_grants_share_one_lock_and_preserve_both_updates(self):
        lock_path = pathlib.Path(f"{self.acl}.lock")
        ready = [self.home / "ready-a", self.home / "ready-b"]
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            processes = [
                subprocess.Popen(
                    [AI_VAULT, "grant", "claude:fixture", user],
                    env={
                        **self.env,
                        "AI_VAULT_TEST_STATE_LOCK_READY": str(marker),
                    },
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for user, marker in zip(("follower-a", "follower-b"), ready)
            ]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not all(path.exists() for path in ready):
                time.sleep(0.01)
            reached_lock = all(path.exists() for path in ready)
            fcntl.flock(lock, fcntl.LOCK_UN)

        results = [process.communicate(timeout=10) + (process.returncode,) for process in processes]
        self.assertTrue(reached_lock, results)
        self.assertEqual([result[2] for result in results], [0, 0], results)
        pullers = json.loads(self.acl.read_text())["profiles"]["claude:fixture"]["pullers"]
        self.assertEqual(set(pullers), {"owner", "follower-a", "follower-b"})
        self.assertEqual(self.acl.stat().st_mode & 0o777, 0o600)

    def test_missing_acl_is_initialized_only_after_taking_the_acl_lock(self):
        self.acl.unlink()
        lock_path = pathlib.Path(f"{self.acl}.lock")
        ready = self.home / "bootstrap-ready"
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(
                [AI_VAULT, "enroll", "codex", "fixture", "owner"],
                env={
                    **self.env,
                    "AI_VAULT_TEST_STATE_LOCK_READY": str(ready),
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not ready.exists():
                time.sleep(0.01)
            reached_lock = ready.exists()
            appeared_while_locked = self.acl.exists()
            fcntl.flock(lock, fcntl.LOCK_UN)

        stdout, stderr = process.communicate(timeout=10)
        self.assertTrue(reached_lock, (stdout, stderr, process.returncode))
        self.assertEqual(process.returncode, 0, (stdout, stderr))
        self.assertFalse(appeared_while_locked)
        state = json.loads(self.acl.read_text())
        self.assertIn("codex:fixture", state["profiles"])
        self.assertEqual(self.acl.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
