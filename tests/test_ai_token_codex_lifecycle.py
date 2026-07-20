import json
import os
import pathlib
import subprocess
import tempfile
import unittest

from support import MockOAuthServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"


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


if __name__ == "__main__":
    unittest.main()
