import hashlib
import json
import pathlib
import stat
import subprocess
import tempfile
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "install-release"


class ReleaseInstallTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = pathlib.Path(self.temporary.name)
        self.install_root = self.directory / "install"

    def tearDown(self):
        self.temporary.cleanup()

    def make_release(self, generation, extra=None):
        files = {
            "ai-token": f"#!/usr/bin/env bash\necho ai-token {generation}\n".encode(),
            "ai-vault": b"#!/usr/bin/env bash\nset -euo pipefail\n",
            "ai-vault-http": b"#!/usr/bin/env python3\nprint('vault-http')\n",
        }
        if extra:
            files.update(extra)
        commit = f"{generation:040x}"
        manifest = {
            "schema": 1,
            "commit": commit,
            "tree": f"{generation + 100:040x}",
            "commit_time": generation,
            "test_command": "tests/run full",
            "files": {
                name: {"sha256": hashlib.sha256(data).hexdigest(), "mode": "0755"}
                for name, data in files.items()
            },
        }
        archive = self.directory / f"release-{generation}.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, data in files.items():
                bundle.writestr(name, data)
            bundle.writestr("MANIFEST.json", json.dumps(manifest))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        pathlib.Path(f"{archive}.sha256").write_text(f"{digest}  {archive.name}\n")
        return archive, commit, digest

    def run_installer(self, command, *arguments):
        return subprocess.run(
            [INSTALLER, command, *map(str, arguments), "--root", self.install_root],
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_two_installs_and_rollback_are_atomic_audited_and_reversible(self):
        first, first_commit, first_digest = self.make_release(1)
        result = self.run_installer("install", first)
        self.assertEqual(result.returncode, 0, result.stderr)
        first_target = (self.install_root / "current").resolve()
        self.assertEqual(first_target.name, f"{first_commit[:12]}-{first_digest[:12]}")
        self.assertEqual(stat.S_IMODE((first_target / "ai-token").stat().st_mode), 0o755)

        second, second_commit, second_digest = self.make_release(2)
        result = self.run_installer("install", second)
        self.assertEqual(result.returncode, 0, result.stderr)
        second_target = (self.install_root / "current").resolve()
        self.assertEqual(second_target.name, f"{second_commit[:12]}-{second_digest[:12]}")
        self.assertEqual((self.install_root / "previous").resolve(), first_target)

        result = self.run_installer("rollback")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.install_root / "current").resolve(), first_target)
        self.assertEqual((self.install_root / "previous").resolve(), second_target)
        events = [json.loads(line) for line in (self.install_root / "deployments.jsonl").read_text().splitlines()]
        self.assertEqual(
            [event["action"] for event in events],
            ["install-intent", "install", "install-intent", "install", "rollback-intent", "rollback"],
        )

    def test_bad_checksum_cannot_change_the_active_release(self):
        first, _commit, _digest = self.make_release(1)
        self.assertEqual(self.run_installer("install", first).returncode, 0)
        active = (self.install_root / "current").resolve()
        second, _commit, _digest = self.make_release(2)
        with second.open("ab") as handle:
            handle.write(b"corrupt")
        result = self.run_installer("install", second)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum", result.stderr)
        self.assertEqual((self.install_root / "current").resolve(), active)

    def test_archive_path_traversal_is_rejected(self):
        archive, _commit, _digest = self.make_release(3, {"../escape": b"no"})
        result = self.run_installer("install", archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe archive path", result.stderr)
        self.assertFalse((self.directory / "escape").exists())


if __name__ == "__main__":
    unittest.main()
