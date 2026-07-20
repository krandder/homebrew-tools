import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"


class HomeResolutionTest(unittest.TestCase):
    def test_nested_codex_profile_home_resolves_the_machine_profile_root(self):
        with tempfile.TemporaryDirectory() as directory:
            machine_home = pathlib.Path(directory)
            nested_home = machine_home / ".codex-profiles" / "adriana"
            auth = machine_home / ".codex-profiles" / "fixture" / ".codex" / "auth.json"
            nested_home.mkdir(parents=True)
            auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "fixture-access",
                    "refresh_token": "__follower_no_refresh__",
                },
            }))
            env = {
                key: value for key, value in os.environ.items()
                if key not in {"AI_TOKEN_REAL_HOME", "CODEX_PROFILES_DIR", "CODEX_CONFIG_DIR", "CODEX_PROFILE"}
            }
            env.update({
                "HOME": str(nested_home),
                "CODEX_PROFILE": "fixture",
                "PATH": "/usr/bin:/bin",
            })
            result = subprocess.run(
                [AI_TOKEN, "codex", "check"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("auth.json present for 'fixture'", result.stdout)
            self.assertFalse((nested_home / ".codex-profiles").exists())

    def test_nested_claude_profile_home_reports_the_machine_profile_root(self):
        with tempfile.TemporaryDirectory() as directory:
            machine_home = pathlib.Path(directory)
            nested_home = machine_home / ".claude-profiles" / "adriana"
            nested_home.mkdir(parents=True)
            env = {
                key: value for key, value in os.environ.items()
                if key not in {"AI_TOKEN_REAL_HOME", "CLAUDE_PROFILES_DIR"}
            }
            env.update({"HOME": str(nested_home), "PATH": "/usr/bin:/bin"})
            result = subprocess.run(
                [AI_TOKEN, "claude", "--diagnose"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"PROFILES_DIR={machine_home / '.claude-profiles'}", result.stderr)
            self.assertFalse((nested_home / ".claude-profiles").exists())

    def test_explicit_real_home_overrides_nested_home_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            nested_home = root / "wrong" / ".codex-profiles" / "adriana"
            real_home = root / "right"
            auth = real_home / ".codex-profiles" / "fixture" / ".codex" / "auth.json"
            nested_home.mkdir(parents=True)
            auth.parent.mkdir(parents=True)
            auth.write_text(json.dumps({
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "fixture-access",
                    "refresh_token": "__follower_no_refresh__",
                },
            }))
            env = {
                key: value for key, value in os.environ.items()
                if key not in {"CODEX_PROFILES_DIR", "CODEX_CONFIG_DIR", "CODEX_PROFILE"}
            }
            env.update({
                "HOME": str(nested_home),
                "AI_TOKEN_REAL_HOME": str(real_home),
                "CODEX_PROFILE": "fixture",
                "PATH": "/usr/bin:/bin",
            })
            result = subprocess.run(
                [AI_TOKEN, "codex", "check"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("auth.json present for 'fixture'", result.stdout)
            self.assertFalse((nested_home / ".codex-profiles").exists())


if __name__ == "__main__":
    unittest.main()
