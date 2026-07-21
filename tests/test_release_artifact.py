import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build-release"
PAYLOAD = (
    "ai-token",
    "ai-vault",
    "ai-vault-http",
    "claude-token",
    "codex-token",
    "setup-claude-token",
    "Formula/ai-token.rb",
    "Formula/ai-vault.rb",
    "Formula/ai-vault-http.rb",
    "Formula/claude-token.rb",
    "Formula/codex-token.rb",
    "tools/build-release",
    "tools/install-release",
    "tools/verify-tdd-history",
    "tools/run-live-canary",
    "tools/report-canary-failure",
    "tools/verify-live-soak",
    "tools/collect-live-soak",
    "tools/audit-live-soak",
    "deploy/canary/farol/ai-token-canary.service",
    "deploy/canary/farol/ai-token-canary.timer",
    "deploy/canary/farol/ai-token-canary-alert@.service",
    "deploy/canary/farol/ai-token-canary-vault.service",
    "deploy/canary/farol/ai-token-soak-audit.service",
    "deploy/canary/farol/ai-token-soak-audit.timer",
    "deploy/canary/agent-1/ai-token-canary.service",
    "deploy/canary/agent-1/ai-token-canary.timer",
    "deploy/canary/agent-1/ai-token-canary-alert@.service",
    "deploy/canary/macos/com.futarchy.ai-token-canary-dispatch.plist",
    "deploy/canary/macos/run-as-ai-token-canary.expect",
    "deploy/canary/macos/run-live",
    "deploy/canary/macos/run-scheduled",
)


class ReleaseArtifactTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        for relative in PAYLOAD:
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
            target.chmod((ROOT / relative).stat().st_mode)
        runner = self.source / "tests" / "run"
        runner.parent.mkdir()
        runner.write_text("#!/usr/bin/env bash\nset -euo pipefail\n[ \"$1\" = full ]\n")
        runner.chmod(0o755)
        subprocess.run(["git", "init", "-q"], cwd=self.source, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.source, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.source, check=True)
        subprocess.run(["git", "add", "."], cwd=self.source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.source, check=True)

    def tearDown(self):
        self.temporary.cleanup()

    def build(self):
        return subprocess.run(
            [BUILDER, "--source", self.source, "--output", self.output],
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_clean_commit_build_is_deterministic_and_self_verifying(self):
        first = self.build()
        self.assertEqual(first.returncode, 0, first.stderr)
        archive = next(self.output.glob("*.zip"))
        checksum = pathlib.Path(f"{archive}.sha256")
        first_bytes = archive.read_bytes()
        expected = hashlib.sha256(first_bytes).hexdigest()
        self.assertEqual(checksum.read_text(), f"{expected}  {archive.name}\n")

        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(set(bundle.namelist()), {*PAYLOAD, "MANIFEST.json"})
            manifest = json.loads(bundle.read("MANIFEST.json"))
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.source, text=True).strip()
            self.assertEqual(manifest["commit"], commit)
            for relative in PAYLOAD:
                self.assertEqual(
                    manifest["files"][relative]["sha256"],
                    hashlib.sha256((self.source / relative).read_bytes()).hexdigest(),
                )

        second = self.build()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(archive.read_bytes(), first_bytes)
        self.assertEqual(len(list(self.output.glob("*.zip"))), 1)

    def test_untracked_write_bits_cannot_change_the_release_artifact(self):
        executable = self.source / "ai-token"
        data = self.source / "deploy/canary/farol/ai-token-canary.service"
        executable.chmod(0o755)
        data.chmod(0o644)
        first = self.build()
        self.assertEqual(first.returncode, 0, first.stderr)
        archive = next(self.output.glob("*.zip"))
        first_bytes = archive.read_bytes()

        executable.chmod(0o775)
        data.chmod(0o664)
        second = self.build()

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(list(self.output.glob("*.zip"))), 1)
        self.assertEqual(archive.read_bytes(), first_bytes)
        with zipfile.ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read("MANIFEST.json"))
        self.assertEqual(manifest["files"]["ai-token"]["mode"], "0755")
        self.assertEqual(
            manifest["files"]["deploy/canary/farol/ai-token-canary.service"]["mode"],
            "0644",
        )

    def test_dirty_tracked_source_is_rejected_before_tests_or_packaging(self):
        with (self.source / "ai-token").open("ab") as handle:
            handle.write(b"dirty")
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tracked worktree is dirty", result.stderr)
        self.assertFalse(self.output.exists())

    def test_checksum_replacement_never_follows_a_destination_symlink(self):
        first = self.build()
        self.assertEqual(first.returncode, 0, first.stderr)
        archive = next(self.output.glob("*.zip"))
        checksum = pathlib.Path(f"{archive}.sha256")
        checksum.unlink()
        victim = self.root / "unrelated-checksum-target"
        victim.write_text("do-not-touch\n")
        checksum.symlink_to(victim)
        before = victim.read_bytes()

        second = self.build()

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(victim.read_bytes(), before)
        self.assertFalse(checksum.is_symlink())
        self.assertEqual(
            checksum.read_text(),
            f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
        )


if __name__ == "__main__":
    unittest.main()
