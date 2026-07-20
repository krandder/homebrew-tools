import importlib.machinery
import importlib.util
import json
import os
import pathlib
import stat
import subprocess
import tempfile
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "run-live-canary"
COMMIT = "a" * 40


class LiveCanaryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.release_root = self.root / "release-store"
        self.release = self.release_root / "releases" / "fixture-release"
        self.release.mkdir(parents=True)
        (self.release_root / "current").symlink_to("releases/fixture-release")
        self.home = self.root / "dedicated-canary-home"
        self.home.mkdir()
        self.credential = (
            self.home / ".claude-profiles" / "canary-fixture" / ".claude" / "credentials.json"
        )
        self.credential.parent.mkdir(parents=True)
        self.credential.write_text("CREDENTIAL_SECRET")
        self.credential.chmod(0o600)
        self.evidence = self.root / "evidence"
        self.calls = self.root / "calls.jsonl"
        self.fail_action = self.root / "fail-action"
        self.config = self.root / "canary.json"
        self.write_fakes()
        self.write_config("leader")

    def tearDown(self):
        self.temporary.cleanup()

    def write_fakes(self):
        installer = self.release / "tools" / "install-release"
        installer.parent.mkdir()
        installer.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            f"calls = pathlib.Path({str(self.calls)!r})\n"
            f"failure = pathlib.Path({str(self.fail_action)!r})\n"
            "with calls.open('a') as handle:\n"
            "    handle.write(json.dumps({'program': 'verify', 'argv': sys.argv[1:], "
            "'home': os.environ.get('HOME'), 'real_home': os.environ.get('AI_TOKEN_REAL_HOME'), "
            "'path': os.environ.get('PATH')}) + '\\n')\n"
            "if failure.exists() and failure.read_text().strip() == 'verify':\n"
            "    print('VERIFIER_SECRET', file=sys.stderr)\n"
            "    raise SystemExit(9)\n"
        )
        installer.chmod(0o755)
        token = self.release / "ai-token"
        token.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            f"calls = pathlib.Path({str(self.calls)!r})\n"
            f"failure = pathlib.Path({str(self.fail_action)!r})\n"
            "action = sys.argv[2] if len(sys.argv) > 2 else ''\n"
            "with calls.open('a') as handle:\n"
            "    handle.write(json.dumps({'program': 'ai-token', 'argv': sys.argv[1:], "
            "'home': os.environ.get('HOME'), 'real_home': os.environ.get('AI_TOKEN_REAL_HOME'), "
            "'profile': os.environ.get('CODEX_USER'), 'authority': "
            "os.environ.get('CLAUDE_TOKEN_VAULT_AUTHORITY'), 'path': os.environ.get('PATH')}) + '\\n')\n"
            "if failure.exists() and failure.read_text().strip() == action:\n"
            "    print('ACCESS_TOKEN_SECRET')\n"
            "    print('REFRESH_TOKEN_SECRET', file=sys.stderr)\n"
            "    raise SystemExit(7)\n"
            f"if action == 'publish':\n    credential = pathlib.Path({str(self.credential)!r})\n"
            "    credential.write_text(credential.read_text() + 'x')\n"
            "    credential.chmod(0o600)\n"
        )
        token.chmod(0o755)

    def write_config(self, role, **updates):
        config = {
            "schema": 1,
            "kind": "claude",
            "profile": "canary-fixture",
            "non_human": True,
            "role": role,
            "home": str(self.home),
            "release_root": str(self.release_root),
            "expect_commit": COMMIT,
            "evidence_dir": str(self.evidence),
        }
        config.update(updates)
        self.config.write_text(json.dumps(config))
        self.config.chmod(0o600)

    def run_canary(self, *arguments, extra_env=None):
        nested = self.root / "ambient" / ".codex-profiles" / "adriana"
        nested.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, "HOME": str(nested), "PATH": "/ambient/decoy"}
        environment.update(extra_env or {})
        return subprocess.run(
            [RUNNER, "--config", self.config, *arguments],
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def recorded_calls(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def evidence_record(self):
        files = list(self.evidence.glob("*.json"))
        self.assertEqual(len(files), 1)
        return files[0], json.loads(files[0].read_text())

    def test_refuses_to_run_without_explicit_live_flag(self):
        result = self.run_canary()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --live", result.stderr)
        self.assertEqual(self.recorded_calls(), [])
        self.assertFalse(self.evidence.exists())

    def test_refuses_a_human_or_undesignated_profile(self):
        for profile, non_human in (("adriana", True), ("canary-fixture", False)):
            with self.subTest(profile=profile, non_human=non_human):
                self.write_config("leader", profile=profile, non_human=non_human)
                result = self.run_canary("--live")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.recorded_calls(), [])

    def test_designation_and_evidence_paths_fail_closed(self):
        real_config = self.root / "real-canary.json"
        self.config.rename(real_config)
        self.config.symlink_to(real_config)
        result = self.run_canary("--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.recorded_calls(), [])

        self.config.unlink()
        real_config.rename(self.config)
        self.config.chmod(0o666)
        result = self.run_canary("--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.recorded_calls(), [])

        self.config.chmod(0o600)
        real_evidence = self.root / "real-evidence"
        real_evidence.mkdir()
        self.evidence.symlink_to(real_evidence, target_is_directory=True)
        result = self.run_canary("--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.recorded_calls(), [])

    def test_current_release_must_resolve_inside_the_release_store(self):
        outside = self.root / "outside-release"
        self.release.rename(outside)
        (self.release_root / "current").unlink()
        (self.release_root / "current").symlink_to(outside)
        result = self.run_canary("--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.recorded_calls(), [])

    def test_leader_uses_verified_release_and_dedicated_home(self):
        result = self.run_canary("--live")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.recorded_calls()
        self.assertEqual([call["program"] for call in calls], ["verify", "ai-token"])
        self.assertEqual(
            calls[0]["argv"],
            ["verify", "--root", str(self.release_root), "--expect-commit", COMMIT],
        )
        self.assertEqual(calls[1]["argv"], ["claude", "publish", "--profile", "canary-fixture"])
        self.assertEqual(calls[1]["home"], str(self.home))
        self.assertEqual(calls[1]["real_home"], str(self.home))
        self.assertEqual(calls[1]["profile"], "canary-fixture")
        self.assertEqual(calls[1]["authority"], "yes")
        self.assertTrue(calls[1]["path"].startswith(str(self.release) + os.pathsep))
        path, record = self.evidence_record()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["profile"], "canary-fixture")
        self.assertEqual(record["steps"], [
            {"name": "verify-release", "returncode": 0},
            {"name": "publish", "returncode": 0},
        ])

    def test_follower_pulls_then_checks_using_the_same_exact_release(self):
        self.write_config("follower")
        result = self.run_canary("--live")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.recorded_calls()
        self.assertEqual(
            [call.get("argv") for call in calls[1:]],
            [
                ["claude", "pull", "--profile", "canary-fixture"],
                ["claude", "check"],
            ],
        )
        for call in calls[1:]:
            self.assertEqual(call["home"], str(self.home))
            self.assertEqual(call["real_home"], str(self.home))
            self.assertTrue(call["path"].startswith(str(self.release) + os.pathsep))
        _path, record = self.evidence_record()
        self.assertEqual(record["status"], "ok")
        self.assertEqual([step["name"] for step in record["steps"]], [
            "verify-release", "pull", "check",
        ])

    def test_macos_follower_refuses_the_shared_login_keychain(self):
        self.write_config("follower")
        fake_modules = self.root / "fake-modules"
        fake_modules.mkdir()
        (fake_modules / "platform.py").write_text("def system(): return 'Darwin'\n")
        result = self.run_canary("--live", extra_env={"PYTHONPATH": str(fake_modules)})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dedicated OS account/keychain", result.stderr)
        self.assertEqual(self.recorded_calls(), [])

    def test_macos_follower_requires_and_accepts_the_exact_dedicated_os_user(self):
        self.write_config("follower", schema=2, os_user="ai-token-canary")
        loader = importlib.machinery.SourceFileLoader("live_canary_runner", str(RUNNER))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        runner = importlib.util.module_from_spec(spec)
        loader.exec_module(runner)

        with (
            mock.patch.object(runner.platform, "system", return_value="Darwin"),
            mock.patch.object(runner.os, "getuid", return_value=502),
            mock.patch.object(
                runner.pwd,
                "getpwuid",
                return_value=types.SimpleNamespace(
                    pw_name="ai-token-canary",
                    pw_dir=str(self.home),
                ),
            ),
        ):
            loaded = runner.load_config(self.config)
        self.assertEqual(loaded["os_user"], "ai-token-canary")

        for actual_user, actual_home in (
            ("kas", self.home),
            ("ai-token-canary", self.root / "wrong-home"),
        ):
            with self.subTest(actual_user=actual_user, actual_home=actual_home):
                with (
                    mock.patch.object(runner.platform, "system", return_value="Darwin"),
                    mock.patch.object(runner.os, "getuid", return_value=502),
                    mock.patch.object(
                        runner.pwd,
                        "getpwuid",
                        return_value=types.SimpleNamespace(
                            pw_name=actual_user,
                            pw_dir=str(actual_home),
                        ),
                    ),
                ):
                    with self.assertRaises(SystemExit):
                        runner.load_config(self.config)

        self.write_config("follower", schema=2, os_user="kas")
        with mock.patch.object(runner.platform, "system", return_value="Darwin"):
            with self.assertRaises(SystemExit):
                runner.load_config(self.config)

    def test_failure_evidence_discards_command_output_and_stops(self):
        self.write_config("follower")
        self.fail_action.write_text("pull")
        result = self.run_canary("--live")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("ACCESS_TOKEN_SECRET", result.stdout + result.stderr)
        self.assertNotIn("REFRESH_TOKEN_SECRET", result.stdout + result.stderr)
        self.assertEqual([call["program"] for call in self.recorded_calls()], ["verify", "ai-token"])
        path, record = self.evidence_record()
        raw = path.read_text()
        self.assertNotIn("ACCESS_TOKEN_SECRET", raw)
        self.assertNotIn("REFRESH_TOKEN_SECRET", raw)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["steps"][-1], {"name": "pull", "returncode": 7})

    def test_failed_release_verification_never_runs_ai_token(self):
        self.fail_action.write_text("verify")
        result = self.run_canary("--live")
        self.assertEqual(result.returncode, 1)
        self.assertEqual([call["program"] for call in self.recorded_calls()], ["verify"])
        self.assertNotIn("VERIFIER_SECRET", result.stdout + result.stderr)
        _path, record = self.evidence_record()
        self.assertEqual(record["steps"], [{"name": "verify-release", "returncode": 9}])

    def test_expected_mutation_is_chained_without_recording_credential_bytes(self):
        first = self.run_canary("--live")
        second = self.run_canary("--live")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.recorded_calls()), 4)
        records = [json.loads(path.read_text()) for path in sorted(self.evidence.glob("*.json"))]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["state_after"], records[1]["state_before"])
        for path in self.evidence.glob("*.json"):
            self.assertNotIn("CREDENTIAL_SECRET", path.read_text())

    def test_unexpected_between_run_writer_fails_before_release_execution(self):
        first = self.run_canary("--live")
        self.assertEqual(first.returncode, 0, first.stderr)
        calls = len(self.recorded_calls())
        self.credential.write_text("UNEXPECTED_WRITER_SECRET")
        self.credential.chmod(0o600)

        second = self.run_canary("--live")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("unexpected credential writer", second.stderr)
        self.assertEqual(len(self.recorded_calls()), calls)
        records = [json.loads(path.read_text()) for path in sorted(self.evidence.glob("*.json"))]
        self.assertEqual(records[-1]["status"], "failed")
        self.assertEqual(records[-1]["steps"], [
            {"name": "writer-continuity", "returncode": 1},
        ])
        self.assertNotIn("UNEXPECTED_WRITER_SECRET", json.dumps(records[-1]))

    def test_credential_state_metadata_rejects_permissive_files(self):
        self.credential.chmod(0o644)
        result = self.run_canary("--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credential state path must be mode 0600", result.stderr)
        self.assertEqual(self.recorded_calls(), [])


if __name__ == "__main__":
    unittest.main()
