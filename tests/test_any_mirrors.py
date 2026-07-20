#!/usr/bin/env python3
"""Hermetic tests for codex-any-mirror and kimi-any-mirror.

Runs the real bash scripts (embedded python heredocs) with the
CODEX_SHARED_DIR / CODEX_PROFILES_DIR and KIMI_SHARED_DIR / KIMI_PROFILES_DIR
env overrides pointed at tmp dirs. Asserts: syncthing-fed shared files
materialize into the leader layout the any-proxies read, refresh tokens are
neutered to "sentinel-follower", publish-metadata keys are stripped, garbage
files (sync-conflict / .suspect / unparseable / tokenless) are skipped, and
the optional single-profile argument mirrors just that profile. No network,
no real HOME.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def codex_payload(access_token):
    return {
        "tokens": {
            "id_token": "id-token",
            "access_token": access_token,
            "refresh_token": "RT-REAL-SECRET",
            "account_id": "acc-1",
        },
        "email": "user@example.com",
        "profile": "alpha",
        "leader": "farol",
        "published_at": "2026-07-20T00:00:00Z",
        "last_refresh": "2026-07-20T00:00:00Z",
    }


def kimi_payload(access_token):
    return {
        "access_token": access_token,
        "refresh_token": "RT-REAL-SECRET",
        "expires_at": 1893456000,
        "scope": "openid profile",
        "profile": "k1",
        "leader": "farol",
        "published_at": "2026-07-20T00:00:00Z",
    }


class MirrorFixture(unittest.TestCase):
    SCRIPT = None      # mirror script in the repo root
    ENV_PREFIX = None  # "CODEX" | "KIMI"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.shared = base / "shared"
        self.profiles = base / "profiles"
        self.home = base / "home"
        for directory in (self.shared, self.profiles, self.home):
            directory.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_shared(self, name, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (self.shared / name).write_text(text)

    def run_mirror(self, *args):
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            f"{self.ENV_PREFIX}_SHARED_DIR": str(self.shared),
            f"{self.ENV_PREFIX}_PROFILES_DIR": str(self.profiles),
        }
        result = subprocess.run(["bash", str(ROOT / self.SCRIPT), *args],
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, f"{self.SCRIPT} failed: {result.stderr}")
        return result

    def mirrored_profiles(self):
        return sorted(p.name for p in self.profiles.iterdir())


class CodexAnyMirrorTest(MirrorFixture):
    SCRIPT = "codex-any-mirror"
    ENV_PREFIX = "CODEX"

    def auth(self, profile):
        return json.loads((self.profiles / profile / ".codex" / "auth.json").read_text())

    def test_materializes_all_profiles_neutered_and_stripped(self):
        self.write_shared("alpha.json", codex_payload("AT-alpha"))
        self.write_shared("beta.json", codex_payload("AT-beta"))
        result = self.run_mirror()
        self.assertIn("2 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), ["alpha", "beta"])
        auth = self.auth("alpha")
        self.assertEqual(auth["tokens"]["access_token"], "AT-alpha")
        self.assertEqual(auth["tokens"]["refresh_token"], "sentinel-follower",
                         "a follower must never hold a real refresh token")
        self.assertEqual(auth["tokens"]["account_id"], "acc-1")
        for key in ("email", "profile", "leader", "published_at"):
            self.assertNotIn(key, auth, f"publish metadata {key!r} must be stripped")
        self.assertEqual(auth["last_refresh"], "2026-07-20T00:00:00Z")

    def test_skips_garbage_files(self):
        self.write_shared("alpha.sync-conflict-20260720-120000.json", codex_payload("AT-stale"))
        self.write_shared("stale.suspect.json", codex_payload("AT-suspect"))
        self.write_shared("broken.json", "{not json")
        self.write_shared("noaccess.json", {"tokens": {"refresh_token": "x"}})
        result = self.run_mirror()
        self.assertIn("0 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), [])

    def test_single_profile_argument(self):
        self.write_shared("alpha.json", codex_payload("AT-alpha"))
        self.write_shared("beta.json", codex_payload("AT-beta"))
        result = self.run_mirror("alpha")
        self.assertIn("1 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), ["alpha"])
        result = self.run_mirror("missing")
        self.assertIn("0 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), ["alpha"])


class KimiAnyMirrorTest(MirrorFixture):
    SCRIPT = "kimi-any-mirror"
    ENV_PREFIX = "KIMI"

    def credentials(self, profile):
        return json.loads((self.profiles / profile / "credentials.json").read_text())

    def test_materializes_all_profiles_neutered_and_stripped(self):
        self.write_shared("k1.json", kimi_payload("AT-k1"))
        self.write_shared("k2.json", kimi_payload("AT-k2"))
        result = self.run_mirror()
        self.assertIn("2 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), ["k1", "k2"])
        cred = self.credentials("k1")
        self.assertEqual(cred["access_token"], "AT-k1")
        self.assertEqual(cred["refresh_token"], "sentinel-follower",
                         "a follower must never hold a real refresh token")
        self.assertEqual(cred["expires_at"], 1893456000)
        self.assertEqual(cred["scope"], "openid profile")
        for key in ("profile", "leader", "published_at"):
            self.assertNotIn(key, cred, f"publish metadata {key!r} must be stripped")

    def test_skips_garbage_files(self):
        self.write_shared("k1.sync-conflict-20260720-120000.json", kimi_payload("AT-stale"))
        self.write_shared("broken.json", "{not json")
        self.write_shared("noaccess.json", {"refresh_token": "x"})
        result = self.run_mirror()
        self.assertIn("0 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), [])

    def test_single_profile_argument(self):
        self.write_shared("k1.json", kimi_payload("AT-k1"))
        self.write_shared("k2.json", kimi_payload("AT-k2"))
        result = self.run_mirror("k1")
        self.assertIn("1 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), ["k1"])
        result = self.run_mirror("missing")
        self.assertIn("0 profile(s) mirrored", result.stdout)
        self.assertEqual(self.mirrored_profiles(), ["k1"])


if __name__ == "__main__":
    unittest.main()
