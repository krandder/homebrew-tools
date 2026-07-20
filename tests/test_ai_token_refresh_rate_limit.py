import json
import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

from support import MockOAuthServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"
NOW = 4_102_444_800


class RefreshRateLimitTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.temporary.name)
        self.profile = "fixture"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "AI_TOKEN_REAL_HOME": str(self.home),
            "AI_TOKEN_REFRESH_STATE_DIR": str(self.home / "refresh-state"),
            "AI_TOKEN_LOG_DIR": str(self.home / "logs"),
            "CODEX_USER": self.profile,
            "CODEX_PROFILES_DIR": str(self.home / "codex-profiles"),
            "CODEX_SHARED_DIR": str(self.home / "shared" / "codex"),
            "KIMI_PROFILES_DIR": str(self.home / "kimi-profiles"),
            "KIMI_SHARED_DIR": str(self.home / "shared" / "kimi"),
            "PATH": "/usr/bin:/bin",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def run_publish(self, kind, server, now):
        env = {**self.env, "AI_TOKEN_TEST_NOW": str(now)}
        if kind == "kimi":
            env["KIMI_CODE_OAUTH_HOST"] = server.token_url.rsplit("/oauth/token", 1)[0]
        else:
            env["CODEX_TOKEN_EP"] = server.token_url
        return subprocess.run(
            [AI_TOKEN, kind, "publish", "--profile", self.profile],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def assert_cooldown_contract(self, kind, credential):
        before = credential.read_bytes()
        with MockOAuthServer(
            429,
            {"error": "rate_limited"},
            token_headers={"Retry-After": "120"},
        ) as server:
            first = self.run_publish(kind, server, NOW)
            second = self.run_publish(kind, server, NOW + 30)
            third = self.run_publish(kind, server, NOW + 121)

        self.assertNotEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        self.assertNotEqual(third.returncode, 0)
        self.assertIn("cooldown", second.stderr)
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(credential.read_bytes(), before)
        local = json.loads(pathlib.Path(f"{credential}.refresh-cooldown").read_text())
        provider = json.loads((self.home / "refresh-state" / f"{kind}.json").read_text())
        self.assertEqual(local["until"], NOW + 241)
        self.assertEqual(provider, local)
        self.assertEqual(stat.S_IMODE(pathlib.Path(f"{credential}.refresh-cooldown").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.home / "refresh-state" / f"{kind}.json").stat().st_mode), 0o600)

    def assert_concurrent_contract(self, kind, server):
        env = {**self.env, "AI_TOKEN_TEST_NOW": str(NOW)}
        if kind == "kimi":
            env["KIMI_CODE_OAUTH_HOST"] = server.token_url.rsplit("/oauth/token", 1)[0]
        else:
            env["CODEX_TOKEN_EP"] = server.token_url
        command = [AI_TOKEN, kind, "publish", "--profile", self.profile]
        processes = [
            subprocess.Popen(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(2)
        ]
        results = [process.communicate(timeout=15) + (process.returncode,) for process in processes]
        self.assertTrue(all(result[2] != 0 for result in results), results)
        self.assertEqual(len(server.requests), 1)

    def test_kimi_honors_retry_after_without_mutating_the_refresh_token(self):
        credential = self.home / "kimi-profiles" / self.profile / "credentials.json"
        credential.parent.mkdir(parents=True)
        credential.write_text(json.dumps({
            "access_token": "expired-access",
            "refresh_token": "real-refresh",
            "expires_at": 1,
        }))
        credential.chmod(0o600)
        self.assert_cooldown_contract("kimi", credential)

    def test_concurrent_kimi_refreshes_collapse_to_one_rate_limited_request(self):
        credential = self.home / "kimi-profiles" / self.profile / "credentials.json"
        credential.parent.mkdir(parents=True)
        credential.write_text(json.dumps({
            "access_token": "expired-access",
            "refresh_token": "real-refresh",
            "expires_at": 1,
        }))
        with MockOAuthServer(
            429,
            {"error": "rate_limited"},
            delay=0.2,
            token_headers={"Retry-After": "120"},
        ) as server:
            self.assert_concurrent_contract("kimi", server)

    def test_codex_honors_retry_after_without_mutating_the_refresh_token(self):
        credential = self.home / "codex-profiles" / self.profile / ".codex" / "auth.json"
        credential.parent.mkdir(parents=True)
        credential.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": "expired-access",
                "refresh_token": "real-refresh",
                "id_token": "fixture-id",
            },
        }))
        credential.chmod(0o600)
        self.assert_cooldown_contract("codex", credential)

    def test_concurrent_codex_refreshes_collapse_to_one_rate_limited_request(self):
        credential = self.home / "codex-profiles" / self.profile / ".codex" / "auth.json"
        credential.parent.mkdir(parents=True)
        credential.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {"access_token": "expired-access", "refresh_token": "real-refresh"},
        }))
        with MockOAuthServer(
            429,
            {"error": "rate_limited"},
            delay=0.2,
            token_headers={"Retry-After": "120"},
        ) as server:
            self.assert_concurrent_contract("codex", server)


if __name__ == "__main__":
    unittest.main()
