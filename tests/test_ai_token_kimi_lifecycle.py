import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"
NOW = 4_102_444_800
SENTINEL = "__follower_no_refresh__"


class KimiLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.temporary.name)
        self.store = self.home / ".kimi-code" / "credentials" / "kimi-code.json"
        self.shared = self.home / "shared" / "fixture.json"
        self.store.parent.mkdir(parents=True)
        self.shared.parent.mkdir(parents=True)
        self.store.write_text(json.dumps({
            "access_token": "previous-access",
            "refresh_token": SENTINEL,
            "expires_at": NOW + 300,
        }))
        self.shared.write_text(json.dumps({
            "access_token": "published-access",
            "refresh_token": SENTINEL,
            "expires_at": NOW + 600,
        }))
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "AI_TOKEN_REAL_HOME": str(self.home),
            "AI_TOKEN_TEST_NOW": str(NOW),
            "KIMI_CODE_STORE": str(self.store),
            "KIMI_SHARED_DIR": str(self.shared.parent),
            "PATH": "/usr/bin:/bin",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def test_follower_pull_never_follows_a_predictable_temporary_symlink(self):
        victim = self.home / "unrelated-state"
        victim.write_text("must-remain-unchanged")
        pathlib.Path(f"{self.store}.tmp").symlink_to(victim)

        result = subprocess.run(
            [AI_TOKEN, "kimi", "pull", "--profile", "fixture"],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(victim.read_text(), "must-remain-unchanged")
        self.assertFalse(self.store.is_symlink())
        self.assertEqual(json.loads(self.store.read_text())["access_token"], "published-access")

    def test_kimi_credential_writers_do_not_use_shared_dot_tmp_paths(self):
        source = AI_TOKEN.read_text()
        kimi = source[source.index("# BACKEND: kimi"):source.index("# ---- generic pairing")]
        self.assertNotIn('tmp=d+".tmp"', kimi)
        self.assertNotIn('tmp=f+".tmp"', kimi)
        self.assertNotIn('tmp = f + ".tmp"', kimi)
        self.assertNotIn('tmp=sf+".tmp"', kimi)


if __name__ == "__main__":
    unittest.main()
