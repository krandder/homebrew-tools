import io
import json
import pathlib
import stat
import subprocess
import tarfile
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "tools" / "collect-live-soak"
SOURCES = ("farol", "agent-1", "macos")


class SoakCollectionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.output = self.root / "collected"

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, source, members=None):
        path = self.root / f"{source}.tar"
        members = members or [(f"{source}-evidence.json", 0o600, b'{"safe":true}\n', "file")]
        with tarfile.open(path, "w") as bundle:
            for name, mode, data, kind in members:
                member = tarfile.TarInfo(name)
                member.mode = mode
                if kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "outside.json"
                    bundle.addfile(member)
                else:
                    member.size = len(data)
                    bundle.addfile(member, io.BytesIO(data))
        return path

    def run_collector(self, archives):
        command = [COLLECTOR, "--output", self.output]
        for source in SOURCES:
            command.extend(["--archive", f"{source}={archives[source]}"])
        return subprocess.run(command, text=True, capture_output=True, timeout=10)

    def test_collects_every_source_atomically_with_safe_manifest(self):
        archives = {}
        expected = {}
        for source in SOURCES:
            records = []
            for index in range(2):
                name = f"2026072{index}-{source}-{index}.json"
                data = json.dumps({"source": source, "index": index}).encode() + b"\n"
                records.append((name, 0o600, data, "file"))
                expected[name] = data
            archives[source] = self.archive(source, records)

        result = self.run_collector(archives)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        self.assertEqual(
            {path.name for path in self.output.glob("*.json")},
            set(expected),
        )
        for name, data in expected.items():
            path = self.output / name
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

        manifest_path = self.output / "COLLECTION.manifest"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(stat.S_IMODE(manifest_path.stat().st_mode), 0o600)
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["sources"], {source: 2 for source in SOURCES})
        self.assertEqual(set(manifest["files"]), set(expected))

    def test_rejects_unsafe_or_incomplete_archives_without_partial_output(self):
        cases = {
            "permissive": [("bad.json", 0o644, b"{}", "file")],
            "symlink": [("bad.json", 0o600, b"", "symlink")],
            "traversal": [("../escape.json", 0o600, b"{}", "file")],
            "nested": [("nested/bad.json", 0o600, b"{}", "file")],
            "appledouble": [("._bad.json", 0o600, b"{}", "file")],
            "non_json": [("bad.txt", 0o600, b"{}", "file")],
        }
        for label, members in cases.items():
            with self.subTest(label=label):
                archives = {source: self.archive(source) for source in SOURCES}
                archives["macos"] = self.archive("macos", members)
                result = self.run_collector(archives)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
                self.assertFalse((self.root / "escape.json").exists())

    def test_rejects_duplicate_names_and_existing_output(self):
        duplicate = [("same.json", 0o600, b"{}", "file")]
        archives = {
            source: self.archive(source, duplicate if source != "macos" else None)
            for source in SOURCES
        }
        result = self.run_collector(archives)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

        self.output.mkdir()
        result = self.run_collector({source: self.archive(source) for source in SOURCES})
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
