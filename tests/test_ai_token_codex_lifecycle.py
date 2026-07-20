import json
import os
import pathlib
import subprocess
import tempfile
import unittest


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

            binary = home / "bin"
            binary.mkdir()
            curl = binary / "curl"
            curl.write_text(
                '#!/usr/bin/env bash\n'
                'printf "%s\\n" "$*" > "$CURL_ARGS"\n'
                'printf \'%s\\n\' \'{"access_token":"new-access","refresh_token":"new-refresh"}\'\n'
            )
            curl.chmod(0o755)
            args = home / "curl-args"
            endpoint = "http://127.0.0.1:1/hermetic-codex-token"
            env = {
                **os.environ,
                "HOME": str(home),
                "AI_TOKEN_REAL_HOME": str(home),
                "CODEX_PROFILES_DIR": str(home / "profiles"),
                "CODEX_SHARED_DIR": str(home / "shared"),
                "CODEX_TOKEN_EP": endpoint,
                "CURL_ARGS": str(args),
                "PATH": f"{binary}:/usr/bin:/bin",
            }

            result = subprocess.run(
                [AI_TOKEN, "codex", "publish", "--profile", "fixture"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(endpoint, args.read_text())


if __name__ == "__main__":
    unittest.main()
