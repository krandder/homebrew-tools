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


class ClaudeLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.temp.name)
        self.profiles = self.home / "profiles"
        self.shared = self.home / "shared"
        self.logs = self.home / "logs"
        self.profile = "fixture"
        self.auth = self.profiles / self.profile / ".claude" / "credentials.json"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "AI_TOKEN_REAL_HOME": str(self.home),
            "CLAUDE_PROFILES_DIR": str(self.profiles),
            "CLAUDE_SHARED_DIR": str(self.shared),
            "CLAUDE_OAUTH_LOCK_DIR": str(self.home / "locks"),
            "AI_TOKEN_LOG_DIR": str(self.logs),
            "PATH": "/usr/bin:/bin",
        }
        for name in (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_TOKEN_VAULT_AUTHORITY",
        ):
            self.env.pop(name, None)

    def tearDown(self):
        self.temp.cleanup()

    def write_credentials(self, authority="vault", expires_at=1, access="old-access", refresh="old-refresh"):
        self.auth.parent.mkdir(parents=True, exist_ok=True)
        self.auth.write_text(json.dumps({
            "claudeAiOauth": {
                "accessToken": access,
                "refreshToken": refresh,
                "expiresAt": expires_at,
            },
            "claudeTokenSync": {"refreshAuthority": authority},
        }))
        self.auth.chmod(0o600)

    def run_publish(self, server, **kwargs):
        env = {**self.env, **kwargs}
        env["CLAUDE_TOKEN_EP"] = server.token_url
        env["CLAUDE_PROFILE_EP"] = server.profile_url
        return subprocess.run(
            [AI_TOKEN, "claude", "publish", "--profile", self.profile],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_invalid_grant_marks_once_and_stops_retrying(self):
        self.write_credentials()
        with MockOAuthServer(400, {"error": "invalid_grant"}) as server:
            first = self.run_publish(server)
            second = self.run_publish(server)

        self.assertNotEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        credential = json.loads(self.auth.read_text())
        self.assertEqual(credential["claudeAiOauth"]["refreshToken"], "old-refresh")
        self.assertTrue(credential["claudeTokenSync"]["needsRelogin"])
        self.assertEqual(len(server.requests), 1)

    def test_transient_failure_preserves_state_and_remains_retryable(self):
        self.write_credentials()
        before = self.auth.read_bytes()
        with MockOAuthServer(503, {"error": "temporarily_unavailable"}) as server:
            first = self.run_publish(server)
            second = self.run_publish(server)

        self.assertNotEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(self.auth.read_bytes(), before)
        self.assertNotIn("needsRelogin", json.loads(self.auth.read_text())["claudeTokenSync"])
        self.assertEqual(len(server.requests), 2)

    def test_owner_authority_refuses_refresh_before_network(self):
        self.write_credentials(authority="owner")
        with MockOAuthServer(200, {}) as server:
            result = self.run_publish(server)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("owner-managed", result.stderr)
        self.assertEqual(server.requests, [])

    def test_success_rotates_atomically_and_publishes_follower(self):
        self.write_credentials()
        token = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 28800,
            "scope": "user:profile user:inference",
        }
        profile = {"account": {"display_name": "Fixture"}, "organization": {"organization_type": "claude_max"}}
        with MockOAuthServer(200, token, 200, profile) as server:
            result = self.run_publish(server)

        self.assertEqual(result.returncode, 0, result.stderr)
        credential = json.loads(self.auth.read_text())
        published = json.loads((self.shared / f"{self.profile}.json").read_text())
        self.assertEqual(credential["claudeAiOauth"]["refreshToken"], "new-refresh")
        self.assertEqual(published["claudeAiOauth"]["refreshToken"], "__follower_no_refresh__")
        self.assertEqual(stat.S_IMODE(self.auth.stat().st_mode), 0o600)
        self.assertFalse(pathlib.Path(str(self.auth) + ".tmp").exists())
        post, get = server.requests
        self.assertEqual(json.loads(post[3])["refresh_token"], "old-refresh")
        self.assertEqual(get[2]["Authorization"], "Bearer new-access")

    def test_concurrent_publish_performs_one_rotation(self):
        self.write_credentials()
        token = {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 28800}
        with MockOAuthServer(200, token, 200, {}, delay=0.2) as server:
            env = {
                **self.env,
                "CLAUDE_TOKEN_EP": server.token_url,
                "CLAUDE_PROFILE_EP": server.profile_url,
            }
            command = [AI_TOKEN, "claude", "publish", "--profile", self.profile]
            processes = [subprocess.Popen(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
            results = [process.communicate(timeout=15) + (process.returncode,) for process in processes]

        self.assertEqual([result[2] for result in results], [0, 0], results)
        self.assertEqual(sum(request[0] == "POST" for request in server.requests), 1)
        self.assertEqual(json.loads(self.auth.read_text())["claudeAiOauth"]["refreshToken"], "new-refresh")


if __name__ == "__main__":
    unittest.main()
