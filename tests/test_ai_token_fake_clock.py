import base64
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

from support import MockOAuthServer


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
        self.write_claude(60)
        self.assertNotEqual(self.run_check("claude").returncode, 0)
        self.write_claude(61)
        self.assertEqual(self.run_check("claude").returncode, 0)

    def test_kimi_follower_freshness_uses_the_injected_clock(self):
        self.write_kimi(60)
        self.assertNotEqual(self.run_check("kimi").returncode, 0)
        self.write_kimi(61)
        self.assertEqual(self.run_check("kimi").returncode, 0)

    def test_kimi_publish_refreshes_at_the_follower_freshness_boundary(self):
        canonical = self.home / "kimi-profiles" / "fixture" / "credentials.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text(json.dumps({
            "access_token": "boundary-access",
            "refresh_token": "real-refresh",
            "expires_at": NOW + 60,
        }))
        token = {
            "access_token": "fresh-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 900,
        }
        with MockOAuthServer(200, token) as server:
            env = {
                **self.env,
                "KIMI_PROFILES_DIR": str(self.home / "kimi-profiles"),
                "KIMI_SHARED_DIR": str(self.home / "kimi-shared"),
                "KIMI_CODE_OAUTH_HOST": server.token_url.rsplit("/oauth/token", 1)[0],
            }
            result = subprocess.run(
                [AI_TOKEN, "kimi", "publish", "--profile", "fixture"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(server.requests), 1)
        published = json.loads((self.home / "kimi-shared" / "fixture.json").read_text())
        self.assertEqual(published["access_token"], "fresh-access")
        self.assertEqual(published["refresh_token"], SENTINEL)

    @staticmethod
    def jwt(expiry):
        payload = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).rstrip(b"=").decode()
        return f"e30.{payload}.sig"

    def test_codex_run_uses_the_same_strict_freshness_boundary(self):
        shared = self.home / "shared" / "codex-tokens" / "fixture.json"
        shared.parent.mkdir(parents=True)
        shared.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": self.jwt(NOW + 60),
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

        value = json.loads(shared.read_text())
        value["tokens"]["access_token"] = self.jwt(NOW + 61)
        shared.write_text(json.dumps(value))
        result = subprocess.run(
            [AI_TOKEN, "codex", "run", "--probe"],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
