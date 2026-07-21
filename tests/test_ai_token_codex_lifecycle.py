import base64
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

from support import MockOAuthServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"


def jwt(expires_at, marker):
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part({'exp': expires_at, 'marker': marker})}.signature"


class CodexLifecycleTest(unittest.TestCase):
    def test_refresh_endpoint_can_be_replaced_by_the_hermetic_lab(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            profile = home / "profiles" / "fixture"
            auth = profile / ".codex" / "auth.json"
            auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                    "id_token": "old-id",
                },
            }))
            (profile / ".role").write_text("leader")

            token = {"access_token": "new-access", "refresh_token": "new-refresh"}
            with MockOAuthServer(200, token) as server:
                env = {
                    **os.environ,
                    "HOME": str(home),
                    "AI_TOKEN_REAL_HOME": str(home),
                    "AI_TOKEN_REFRESH_STATE_DIR": str(home / "refresh-state"),
                    "CODEX_PROFILES_DIR": str(home / "profiles"),
                    "CODEX_SHARED_DIR": str(home / "shared"),
                    "CODEX_TOKEN_EP": server.token_url,
                    "PATH": "/usr/bin:/bin",
                }

                result = subprocess.run(
                    [AI_TOKEN, "codex", "publish", "--profile", "fixture"],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=10,
                )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(server.requests), 1)
            self.assertIn(b"refresh_token=old-refresh", server.requests[0][3])
            self.assertEqual(json.loads(auth.read_text())["tokens"]["refresh_token"], "new-refresh")

    def test_crash_before_shared_replace_preserves_previous_follower_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            profile = home / "profiles" / "fixture"
            auth = profile / ".codex" / "auth.json"
            shared = home / "shared" / "fixture.json"
            auth.parent.mkdir(parents=True)
            shared.parent.mkdir()
            now = int(time.time())
            auth.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": jwt(now + 3600, "current"),
                    "refresh_token": "real-refresh",
                },
            }))
            (profile / ".role").write_text("leader")
            shared.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": jwt(now + 3600, "previous"),
                    "refresh_token": "__follower_no_refresh__",
                },
            }))
            shared.chmod(0o600)
            before = shared.read_bytes()
            result = subprocess.run(
                [AI_TOKEN, "codex", "publish", "--profile", "fixture"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "AI_TOKEN_REAL_HOME": str(home),
                    "CODEX_PROFILES_DIR": str(home / "profiles"),
                    "CODEX_SHARED_DIR": str(home / "shared"),
                    "AI_TOKEN_TEST_NOW": str(now),
                    "AI_TOKEN_TEST_CRASH_AT": "before-codex-shared-replace",
                    "PATH": "/usr/bin:/bin",
                },
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(shared.read_bytes(), before)
            json.loads(shared.read_text())

    def test_crash_before_follower_replace_preserves_previous_local_auth(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            profile = home / "profiles" / "fixture"
            auth = profile / ".codex" / "auth.json"
            shared = home / "shared" / "fixture.json"
            auth.parent.mkdir(parents=True)
            shared.parent.mkdir()
            now = int(time.time())
            auth.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": jwt(now + 3600, "previous-local"),
                    "refresh_token": "__follower_no_refresh__",
                },
            }))
            (profile / ".role").write_text("follower")
            shared.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": jwt(now + 3600, "published"),
                    "refresh_token": "__follower_no_refresh__",
                },
            }))
            shared.chmod(0o600)
            before = auth.read_bytes()
            result = subprocess.run(
                [AI_TOKEN, "codex", "pull", "--profile", "fixture"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "AI_TOKEN_REAL_HOME": str(home),
                    "CODEX_PROFILES_DIR": str(home / "profiles"),
                    "CODEX_SHARED_DIR": str(home / "shared"),
                    "AI_TOKEN_TEST_NOW": str(now),
                    "AI_TOKEN_TEST_CRASH_AT": "before-codex-follower-replace",
                    "PATH": "/usr/bin:/bin",
                },
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(auth.read_bytes(), before)
            json.loads(auth.read_text())

    def test_crash_before_sentinel_replace_preserves_owner_auth_and_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            profile = home / "profiles" / "fixture"
            auth = profile / ".codex" / "auth.json"
            binary = home / "bin"
            auth.parent.mkdir(parents=True)
            binary.mkdir()
            now = int(time.time())
            auth.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": jwt(now + 3600, "owner"),
                    "refresh_token": "real-refresh",
                },
            }))
            role = profile / ".role"
            role.write_text("leader")
            ssh = binary / "ssh"
            ssh.write_text("#!/bin/sh\ncat >/dev/null\n")
            ssh.chmod(0o755)
            before = auth.read_bytes()
            result = subprocess.run(
                [AI_TOKEN, "codex", "push", "--profile", "fixture"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "AI_TOKEN_REAL_HOME": str(home),
                    "CODEX_PROFILES_DIR": str(home / "profiles"),
                    "CODEX_SHARED_DIR": str(home / "shared"),
                    "AI_TOKEN_TEST_NOW": str(now),
                    "AI_TOKEN_TEST_CRASH_AT": "before-codex-sentinel-replace",
                    "PATH": f"{binary}:/usr/bin:/bin",
                },
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(auth.read_bytes(), before)
            self.assertEqual(role.read_text(), "leader")


if __name__ == "__main__":
    unittest.main()
