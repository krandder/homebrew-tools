import fcntl
import datetime
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest
import random


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_VAULT = ROOT / "ai-vault"


class VaultReceiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.temp.name)
        self.state = self.home / "state"
        self.profiles = self.home / "profiles"
        self.shared = self.home / "shared"
        self.bin = self.home / "bin"
        self.calls = self.home / "calls"
        self.bin.mkdir()
        fake = self.bin / "ai-token"
        fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$AI_TOKEN_CALLS"\n')
        fake.chmod(0o755)
        self.state.mkdir()
        (self.state / "acl.json").write_text(json.dumps({
            "operator": "owner",
            "admins": [],
            "profiles": {
                "claude:fixture": {"owner": "owner", "pullers": ["owner"], "kind": "claude"},
                "kimi:fixture": {"owner": "owner", "pullers": ["owner"], "kind": "kimi"},
                "codex:fixture": {"owner": "owner", "pullers": ["owner"], "kind": "codex"},
            },
        }))
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CODEX_VAULT_USER": "owner",
            "CODEX_VAULT_DIR": str(self.state),
            "CODEX_PROFILES_DIR": str(self.home / "codex-profiles"),
            "CLAUDE_PROFILES_DIR": str(self.profiles),
            "CODEX_SHARED_DIR": str(self.home / "codex-shared"),
            "CLAUDE_SHARED_DIR": str(self.shared),
            "KIMI_PROFILES_DIR": str(self.home / "kimi-profiles"),
            "KIMI_SHARED_DIR": str(self.home / "kimi-shared"),
            "AI_TOKEN_CALLS": str(self.calls),
            "PATH": f"{self.bin}:/usr/bin:/bin",
        }
        self.canonical = self.profiles / "fixture" / ".claude" / "credentials.json"
        self.kimi_canonical = self.home / "kimi-profiles" / "fixture" / "credentials.json"
        self.kimi_shared = self.home / "kimi-shared" / "fixture.json"
        self.codex_canonical = self.home / "codex-profiles" / "fixture" / ".codex" / "auth.json"

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def credentials(access, refresh, expires):
        return {
            "claudeAiOauth": {
                "accessToken": access,
                "refreshToken": refresh,
                "expiresAt": expires,
            }
        }

    def receive(self, value):
        return subprocess.run(
            [AI_VAULT, "receive", "claude:fixture"],
            input=json.dumps(value),
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def kimi_sync(self, value):
        return subprocess.run(
            [AI_VAULT, "sync-receive", "kimi:fixture"],
            input=json.dumps(value),
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def claude_sync(self, value):
        return subprocess.run(
            [AI_VAULT, "sync-receive", "claude:fixture"],
            input=json.dumps(value),
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def codex_receive(self, value):
        return subprocess.run(
            [AI_VAULT, "receive", "codex:fixture"],
            input=json.dumps(value),
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    @staticmethod
    def kimi_credentials(access, refresh, expires):
        return {
            "access_token": access,
            "refresh_token": refresh,
            "expires_at": expires,
        }

    @staticmethod
    def codex_credentials(access, refresh, generation=None):
        value = {
            "auth_mode": "chatgpt",
            "tokens": {"access_token": access, "refresh_token": refresh},
        }
        if generation is not None:
            value["last_refresh"] = generation
        return value

    def test_receive_invokes_the_selected_ai_token_backend(self):
        result = self.receive(self.credentials("access", "refresh", 4102444800000))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text().strip(), "claude publish --profile fixture")

    def test_stale_snapshot_cannot_replace_canonical(self):
        self.assertEqual(self.receive(self.credentials("new", "new-refresh", 4102444800000)).returncode, 0)
        before = self.canonical.read_bytes()
        stale = self.receive(self.credentials("old", "old-refresh", 4102444700000))
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.canonical.read_bytes(), before)

    def test_conflicting_rotation_at_same_expiry_is_rejected(self):
        self.assertEqual(self.receive(self.credentials("first", "first-refresh", 4102444800000)).returncode, 0)
        before = self.canonical.read_bytes()
        conflict = self.receive(self.credentials("conflict", "other-refresh", 4102444800000))
        self.assertNotEqual(conflict.returncode, 0)
        self.assertEqual(self.canonical.read_bytes(), before)

    def test_newer_rotation_replaces_canonical(self):
        self.assertEqual(self.receive(self.credentials("first", "first-refresh", 4102444800000)).returncode, 0)
        newer = self.receive(self.credentials("second", "second-refresh", 4102444900000))
        self.assertEqual(newer.returncode, 0, newer.stderr)
        stored = json.loads(self.canonical.read_text())
        self.assertEqual(stored["claudeAiOauth"]["refreshToken"], "second-refresh")
        self.assertEqual(stored["claudeTokenSync"]["refreshAuthority"], "vault")

    def test_follower_sentinel_is_rejected(self):
        result = self.receive(self.credentials("access", "__follower_no_refresh__", 4102444800000))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.canonical.exists())

    def test_unversioned_claude_snapshot_is_rejected(self):
        result = self.receive(self.credentials("access", "refresh", 0))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.canonical.exists())

    def test_claude_freshness_uses_the_injected_clock(self):
        now = 4_102_444_800
        self.env["AI_TOKEN_TEST_NOW"] = str(now)
        result = self.claude_sync(self.credentials("access", "refresh", (now + 59) * 1000))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.canonical.exists())

    def test_malformed_canonical_fails_closed(self):
        self.canonical.parent.mkdir(parents=True)
        self.canonical.write_text("{")
        before = self.canonical.read_bytes()
        result = self.receive(self.credentials("access", "refresh", 4102444800000))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.canonical.read_bytes(), before)

    def test_kimi_owner_sync_publishes_only_a_follower_token(self):
        expires = int(time.time()) + 900
        result = self.kimi_sync(self.kimi_credentials("access", "owner-refresh", expires))
        self.assertEqual(result.returncode, 0, result.stderr)
        canonical = json.loads(self.kimi_canonical.read_text())
        follower = json.loads(self.kimi_shared.read_text())
        self.assertEqual(canonical["refresh_token"], "owner-refresh")
        self.assertEqual(canonical["kimiTokenSync"]["refreshAuthority"], "owner")
        self.assertEqual(follower["refresh_token"], "__follower_no_refresh__")
        self.assertEqual(self.kimi_canonical.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.kimi_shared.stat().st_mode & 0o777, 0o600)

    def test_stale_kimi_owner_snapshot_cannot_replace_canonical(self):
        expires = int(time.time()) + 900
        self.assertEqual(self.kimi_sync(self.kimi_credentials("new", "new-refresh", expires)).returncode, 0)
        before = self.kimi_canonical.read_bytes()
        stale = self.kimi_sync(self.kimi_credentials("old", "old-refresh", expires - 60))
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.kimi_canonical.read_bytes(), before)

    def test_conflicting_kimi_rotation_at_same_expiry_is_rejected(self):
        expires = int(time.time()) + 900
        self.assertEqual(self.kimi_sync(self.kimi_credentials("first", "first-refresh", expires)).returncode, 0)
        before = self.kimi_canonical.read_bytes()
        conflict = self.kimi_sync(self.kimi_credentials("second", "other-refresh", expires))
        self.assertNotEqual(conflict.returncode, 0)
        self.assertEqual(self.kimi_canonical.read_bytes(), before)

    def test_unversioned_kimi_snapshot_is_rejected(self):
        result = self.kimi_sync(self.kimi_credentials("access", "refresh", 0))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.kimi_canonical.exists())

    def test_kimi_freshness_uses_the_injected_clock(self):
        now = 4_102_444_800
        self.env["AI_TOKEN_TEST_NOW"] = str(now)
        result = self.kimi_sync(self.kimi_credentials("access", "refresh", now + 59))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.kimi_canonical.exists())

    def test_malformed_kimi_canonical_fails_closed(self):
        self.kimi_canonical.parent.mkdir(parents=True)
        self.kimi_canonical.write_text("{")
        before = self.kimi_canonical.read_bytes()
        result = self.kimi_sync(self.kimi_credentials("access", "refresh", int(time.time()) + 900))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.kimi_canonical.read_bytes(), before)

    def test_concurrent_kimi_generations_finish_on_the_newest(self):
        expires = int(time.time()) + 900
        self.kimi_canonical.parent.mkdir(parents=True)
        lock_path = pathlib.Path(f"{self.kimi_canonical}.lock")
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            processes = []
            for value in (
                self.kimi_credentials("older", "older-refresh", expires),
                self.kimi_credentials("newest", "newest-refresh", expires + 60),
            ):
                process = subprocess.Popen(
                    [AI_VAULT, "sync-receive", "kimi:fixture"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=self.env,
                    text=True,
                )
                process.stdin.write(json.dumps(value))
                process.stdin.close()
                processes.append(process)
            fcntl.flock(lock, fcntl.LOCK_UN)

        for process in processes:
            returncode = process.wait(timeout=10)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()
            self.assertIn(returncode, (0, 1), stderr)
        stored = json.loads(self.kimi_canonical.read_text())
        self.assertEqual(stored["access_token"], "newest")
        self.assertEqual(stored["refresh_token"], "newest-refresh")

    def test_unversioned_codex_snapshot_is_rejected(self):
        result = self.codex_receive(self.codex_credentials("access", "refresh"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.codex_canonical.exists())

    def test_stale_codex_snapshot_cannot_replace_canonical(self):
        newer = "2026-07-20T14:00:00+00:00"
        older = "2026-07-20T13:00:00+00:00"
        self.assertEqual(self.codex_receive(self.codex_credentials("new", "new-refresh", newer)).returncode, 0)
        before = self.codex_canonical.read_bytes()
        stale = self.codex_receive(self.codex_credentials("old", "old-refresh", older))
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.codex_canonical.read_bytes(), before)

    def test_conflicting_codex_rotation_at_same_generation_is_rejected(self):
        generation = "2026-07-20T14:00:00+00:00"
        self.assertEqual(self.codex_receive(self.codex_credentials("first", "first-refresh", generation)).returncode, 0)
        before = self.codex_canonical.read_bytes()
        conflict = self.codex_receive(self.codex_credentials("second", "other-refresh", generation))
        self.assertNotEqual(conflict.returncode, 0)
        self.assertEqual(self.codex_canonical.read_bytes(), before)

    def test_newer_codex_rotation_replaces_canonical(self):
        older = "2026-07-20T13:00:00+00:00"
        newer = "2026-07-20T14:00:00+00:00"
        self.assertEqual(self.codex_receive(self.codex_credentials("old", "old-refresh", older)).returncode, 0)
        result = self.codex_receive(self.codex_credentials("new", "new-refresh", newer))
        self.assertEqual(result.returncode, 0, result.stderr)
        stored = json.loads(self.codex_canonical.read_text())
        self.assertEqual(stored["tokens"]["refresh_token"], "new-refresh")

    def exercise_generated_generations(self, receive, credentials, canonical, refresh_from):
        rng = random.Random(97)
        events = [(generation, f"refresh-{generation}") for generation in range(1, 11)]
        events += [(generation, f"conflict-{generation}") for generation in range(1, 11)]
        rng.shuffle(events)
        current_generation = None
        current_refresh = None
        for generation, refresh in events:
            result = receive(credentials(generation, refresh))
            accepted = (
                current_generation is None
                or generation > current_generation
                or (generation == current_generation and refresh == current_refresh)
            )
            self.assertEqual(result.returncode == 0, accepted, result.stderr)
            if accepted:
                current_generation, current_refresh = generation, refresh
            stored = json.loads(canonical.read_text())
            self.assertEqual(refresh_from(stored), current_refresh)

    def test_generated_claude_generations_match_the_reference_rule(self):
        self.exercise_generated_generations(
            self.receive,
            lambda generation, refresh: self.credentials(f"access-{generation}", refresh, generation * 1000),
            self.canonical,
            lambda value: value["claudeAiOauth"]["refreshToken"],
        )

    def test_generated_kimi_generations_match_the_reference_rule(self):
        now = 4_102_444_800
        self.env["AI_TOKEN_TEST_NOW"] = str(now)
        self.exercise_generated_generations(
            self.kimi_sync,
            lambda generation, refresh: self.kimi_credentials(f"access-{generation}", refresh, now + 1000 + generation),
            self.kimi_canonical,
            lambda value: value["refresh_token"],
        )

    def test_generated_codex_generations_match_the_reference_rule(self):
        base = datetime.datetime(2026, 7, 20, tzinfo=datetime.timezone.utc)
        self.exercise_generated_generations(
            self.codex_receive,
            lambda generation, refresh: self.codex_credentials(
                f"access-{generation}", refresh, (base + datetime.timedelta(seconds=generation)).isoformat()
            ),
            self.codex_canonical,
            lambda value: value["tokens"]["refresh_token"],
        )


if __name__ == "__main__":
    unittest.main()
