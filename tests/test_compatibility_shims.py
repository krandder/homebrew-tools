import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CompatibilityShimTest(unittest.TestCase):
    def test_legacy_entrypoints_are_thin_canonical_shims(self):
        with tempfile.TemporaryDirectory() as directory:
            shadow = pathlib.Path(directory) / "ai-token"
            shadow.write_text("#!/usr/bin/env bash\necho stale-path-writer\n")
            shadow.chmod(0o755)
            env = {**os.environ, "PATH": f"{directory}:/usr/bin:/bin"}
            for name, backend in (("claude-token", "claude"), ("codex-token", "codex")):
                with self.subTest(entrypoint=name):
                    canonical = subprocess.run(
                        [ROOT / "ai-token", backend, "--version"],
                        env=env,
                        text=True,
                        capture_output=True,
                        timeout=10,
                        check=True,
                    ).stdout
                    path = ROOT / name
                    source = path.read_text()
                    self.assertLessEqual(len(source.splitlines()), 15, "shim must not duplicate credential logic")
                    self.assertIn("exec", source)
                    result = subprocess.run(
                        [path, "--version"],
                        env=env,
                        text=True,
                        capture_output=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, canonical)


if __name__ == "__main__":
    unittest.main()
