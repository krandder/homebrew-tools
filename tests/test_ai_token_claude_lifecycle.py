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
            "AI_TOKEN_REFRESH_STATE_DIR": str(self.home / "refresh-state"),
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

    def test_rate_limit_persists_retry_after_and_blocks_refresh_hammering(self):
        self.write_credentials()
        before = self.auth.read_bytes()
        now = 4_102_444_800
        with MockOAuthServer(
            429,
            {"error": "rate_limited"},
            token_headers={"Retry-After": "120"},
        ) as server:
            first = self.run_publish(server, AI_TOKEN_TEST_NOW=str(now))
            second = self.run_publish(server, AI_TOKEN_TEST_NOW=str(now + 30))
            third = self.run_publish(server, AI_TOKEN_TEST_NOW=str(now + 121))

        self.assertNotEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        self.assertNotEqual(third.returncode, 0)
        self.assertEqual(self.auth.read_bytes(), before)
        self.assertEqual(len(server.requests), 2)
        self.assertIn("cooldown", second.stderr)
        cooldown = json.loads(pathlib.Path(f"{self.auth}.refresh-cooldown").read_text())
        self.assertEqual(cooldown["until"], now + 241)

    def test_rate_limit_on_one_profile_blocks_other_profiles_on_the_same_ip(self):
        self.write_credentials()
        other = self.profiles / "other" / ".claude" / "credentials.json"
        other.parent.mkdir(parents=True)
        other.write_text(self.auth.read_text())
        other.chmod(0o600)
        now = 4_102_444_800
        with MockOAuthServer(429, {"error": "rate_limited"}, token_headers={"Retry-After": "120"}) as server:
            first = self.run_publish(server, AI_TOKEN_TEST_NOW=str(now))
            env = {
                **self.env,
                "AI_TOKEN_TEST_NOW": str(now),
                "CLAUDE_TOKEN_EP": server.token_url,
                "CLAUDE_PROFILE_EP": server.profile_url,
            }
            second = subprocess.run(
                [AI_TOKEN, "claude", "publish", "--profile", "other"],
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
            )

        self.assertNotEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("cooldown", second.stderr)
        self.assertEqual(len(server.requests), 1)
        self.assertFalse(pathlib.Path(f"{other}.refresh-cooldown").exists())

    def test_concurrent_rate_limited_publishes_make_one_network_request(self):
        self.write_credentials()
        now = 4_102_444_800
        with MockOAuthServer(
            429,
            {"error": "rate_limited"},
            delay=0.2,
            token_headers={"Retry-After": "120"},
        ) as server:
            env = {
                **self.env,
                "AI_TOKEN_TEST_NOW": str(now),
                "CLAUDE_TOKEN_EP": server.token_url,
                "CLAUDE_PROFILE_EP": server.profile_url,
            }
            command = [AI_TOKEN, "claude", "publish", "--profile", self.profile]
            processes = [
                subprocess.Popen(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(2)
            ]
            results = [process.communicate(timeout=15) + (process.returncode,) for process in processes]

        self.assertTrue(all(result[2] != 0 for result in results), results)
        self.assertEqual(len(server.requests), 1)

    def test_owner_authority_refuses_refresh_before_network(self):
        self.write_credentials(authority="owner")
        with MockOAuthServer(200, {}) as server:
            result = self.run_publish(server)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("owner-managed", result.stderr)
        self.assertEqual(server.requests, [])

    def test_refresh_threshold_uses_the_injected_clock(self):
        now = 4_102_444_800
        token = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 28_800,
        }
        with MockOAuthServer(200, token, 200, {}) as server:
            self.write_credentials(expires_at=(now + 9_000) * 1000)
            exact = self.run_publish(server, AI_TOKEN_TEST_NOW=str(now))
            self.assertEqual(exact.returncode, 0, exact.stderr)
            self.assertEqual(server.requests, [])
            published = json.loads((self.shared / f"{self.profile}.json").read_text())
            self.assertEqual(published["claudeAiOauth"]["accessToken"], "old-access")

            self.write_credentials(expires_at=(now + 8_999) * 1000)
            below = self.run_publish(server, AI_TOKEN_TEST_NOW=str(now))
            self.assertEqual(below.returncode, 0, below.stderr)
            self.assertEqual(sum(request[0] == "POST" for request in server.requests), 1)
            published = json.loads((self.shared / f"{self.profile}.json").read_text())
            self.assertEqual(published["claudeAiOauth"]["accessToken"], "new-access")

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

    def test_crashes_before_refresh_replacements_never_truncate_credentials(self):
        self.write_credentials()
        self.shared.mkdir()
        published_path = self.shared / f"{self.profile}.json"
        published_path.write_text(json.dumps({
            "claudeAiOauth": {
                "accessToken": "previous-access",
                "refreshToken": "__follower_no_refresh__",
            },
        }))
        published_path.chmod(0o600)
        old_auth = self.auth.read_bytes()
        old_published = published_path.read_bytes()
        token = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 28_800,
        }

        with MockOAuthServer(200, token, 200, {}) as server:
            canonical_crash = self.run_publish(
                server, AI_TOKEN_TEST_CRASH_AT="before-claude-canonical-replace",
            )
            self.assertNotEqual(canonical_crash.returncode, 0)
            self.assertEqual(self.auth.read_bytes(), old_auth)
            self.assertEqual(published_path.read_bytes(), old_published)
            json.loads(self.auth.read_text())
            json.loads(published_path.read_text())

            shared_crash = self.run_publish(
                server, AI_TOKEN_TEST_CRASH_AT="before-claude-shared-replace",
            )
            self.assertNotEqual(shared_crash.returncode, 0)
            self.assertEqual(
                json.loads(self.auth.read_text())["claudeAiOauth"]["refreshToken"],
                "new-refresh",
            )
            self.assertEqual(published_path.read_bytes(), old_published)
            json.loads(published_path.read_text())

            recovered = self.run_publish(server)

        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(
            json.loads(published_path.read_text())["claudeAiOauth"]["accessToken"],
            "new-access",
        )
        self.assertFalse(list(self.auth.parent.glob(f".{self.auth.name}.token-*")))
        self.assertFalse(list(self.shared.glob(f".{published_path.name}.token-*")))
        self.assertEqual(sum(request[0] == "POST" for request in server.requests), 2)

    def test_crash_before_fresh_publish_preserves_previous_shared_credential(self):
        self.write_credentials(expires_at=4_102_454_800_000)
        self.shared.mkdir()
        published_path = self.shared / f"{self.profile}.json"
        published_path.write_text(json.dumps({
            "claudeAiOauth": {
                "accessToken": "previous-access",
                "refreshToken": "__follower_no_refresh__",
            },
        }))
        published_path.chmod(0o600)
        before = published_path.read_bytes()

        with MockOAuthServer(200, {}) as server:
            result = self.run_publish(
                server,
                AI_TOKEN_TEST_NOW="4102444800",
                AI_TOKEN_TEST_CRASH_AT="before-claude-shared-replace",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(published_path.read_bytes(), before)
        json.loads(published_path.read_text())
        self.assertEqual(server.requests, [])

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
