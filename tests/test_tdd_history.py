import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify-tdd-history"


class TddHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.repo, check=True)
        (self.repo / "tests").mkdir()
        (self.repo / "ai-token").write_text("old\n")
        (self.repo / "tests" / "test_check.py").write_text(
            "import pathlib\n"
            "assert pathlib.Path('ai-token').read_text() == 'old\\n'\n"
        )
        self.commit("base")
        self.base = self.rev()

    def tearDown(self):
        self.temporary.cleanup()

    def commit(self, message):
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=self.repo, check=True)

    def rev(self):
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()

    def verify(self):
        return subprocess.run(
            [VERIFIER, "--base", self.base, "--head", self.rev(), "--", sys.executable, "tests/test_check.py"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_accepts_a_failing_test_only_commit_before_the_green_change(self):
        (self.repo / "tests" / "test_check.py").write_text(
            "import pathlib\n"
            "assert pathlib.Path('ai-token').read_text() == 'new\\n'\n"
        )
        self.commit("test: require new behavior")
        (self.repo / "ai-token").write_text("new\n")
        self.commit("feat: implement new behavior")

        result = self.verify()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified red-before-green", result.stdout)

    def test_rejects_production_change_without_an_earlier_test_only_commit(self):
        (self.repo / "ai-token").write_text("new\n")
        (self.repo / "tests" / "test_check.py").write_text(
            "import pathlib\n"
            "assert pathlib.Path('ai-token').read_text() == 'new\\n'\n"
        )
        self.commit("feat: tests added after implementation")

        result = self.verify()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no preceding test-only red commit", result.stderr)

    def test_rejects_a_candidate_red_commit_whose_suite_was_green(self):
        (self.repo / "tests" / "test_check.py").write_text(
            "import pathlib\n"
            "assert pathlib.Path('ai-token').read_text() == 'old\\n'\n"
            "assert True\n"
        )
        self.commit("test: still green")
        (self.repo / "ai-token").write_text("new\n")
        self.commit("feat: unproven behavior")

        result = self.verify()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("candidate red commit unexpectedly passed", result.stderr)


if __name__ == "__main__":
    unittest.main()
