import pathlib
import subprocess
import tempfile
import textwrap
import unittest


RUNNER = pathlib.Path(__file__).with_name("run-unittest")


class StrictUnittestTest(unittest.TestCase):
    def run_case(self, body):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "test_case.py"
            path.write_text(textwrap.dedent(body))
            return subprocess.run(
                [RUNNER, temporary, "test_case.py"], text=True, capture_output=True
            )

    def test_passes_an_ordinary_green_suite(self):
        result = self.run_case("""
            import unittest
            class Case(unittest.TestCase):
                def test_green(self): self.assertTrue(True)
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fails_a_skipped_test(self):
        result = self.run_case("""
            import unittest
            class Case(unittest.TestCase):
                @unittest.skip("fixture skip")
                def test_skipped(self): pass
        """)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skips and expected failures are failures", result.stderr)

    def test_fails_an_expected_failure(self):
        result = self.run_case("""
            import unittest
            class Case(unittest.TestCase):
                @unittest.expectedFailure
                def test_expected_failure(self): self.fail()
        """)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skips and expected failures are failures", result.stderr)


if __name__ == "__main__":
    unittest.main()
