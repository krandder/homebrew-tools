import base64
import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"
SENTINEL = "__follower_no_refresh__"
NOW = 4_102_444_800


class FakeClockTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.temporary.name)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "AI_TOKEN_REAL_HOME": str(self.home),
            "AI_TOKEN_TEST_NOW": str(NOW),
            "PATH": "/usr/bin:/bin",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def run_check(self, kind):
        return subprocess.run(
            [AI_TOKEN, kind, "check"],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def write_claude(self, seconds_from_now):
        path = self.home / ".claude" / ".credentials.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "accessToken": "fixture-access",
            "refreshToken": SENTINEL,
            "expiresAt": (NOW + seconds_from_now) * 1000,
        }))

    def write_kimi(self, seconds_from_now):
        path = self.home / ".kimi-code" / "credentials" / "kimi-code.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "access_token": "fixture-access",
            "refresh_token": SENTINEL,
            "expires_at": NOW + seconds_from_now,
        }))

    def test_claude_follower_freshness_uses_the_injected_clock(self):
        self.write_claude(59)
        self.assertNotEqual(self.run_check("claude").returncode, 0)
        self.write_claude(61)
        self.assertEqual(self.run_check("claude").returncode, 0)

    def test_kimi_follower_freshness_uses_the_injected_clock(self):
        self.write_kimi(59)
        self.assertNotEqual(self.run_check("kimi").returncode, 0)
        self.write_kimi(61)
        self.assertEqual(self.run_check("kimi").returncode, 0)

    @staticmethod
    def jwt(expiry):
        payload = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).rstrip(b"=").decode()
        return f"e30.{payload}.sig"

    def test_codex_run_rejects_an_expired_published_token_before_launch(self):
        shared = self.home / "shared" / "codex-tokens" / "fixture.json"
        shared.parent.mkdir(parents=True)
        shared.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": self.jwt(NOW + 59),
                "refresh_token": SENTINEL,
            },
        }))
        marker = self.home / "launched"
        executable = self.home / "codex-real"
        executable.write_text(f"#!/usr/bin/env bash\ntouch {marker}\n")
        executable.chmod(0o755)
        env = {
            **self.env,
            "CODEX_USER": "fixture",
            "AI_TOKEN_MODE": "follower",
            "CODEX_BIN": str(executable),
        }
        result = subprocess.run(
            [AI_TOKEN, "codex", "run", "--probe"],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
