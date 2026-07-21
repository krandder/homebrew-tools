import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "tools" / "audit-live-soak"


class LiveSoakAuditTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.calls = self.root / "calls.jsonl"
        self.config = self.root / "canary.json"
        self.config.write_text(json.dumps({
            "profile": "canary-fixture",
            "expect_commit": "a" * 40,
        }))
        self.collector = self.fake("collector", """
import json, os, pathlib, sys
out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
out.mkdir()
with open(os.environ['AUDIT_CALLS'], 'a') as handle:
    handle.write(json.dumps(['collector', *sys.argv[1:]]) + '\\n')
""")
        self.verifier = self.fake("verifier", """
import json, os, sys
with open(os.environ['AUDIT_CALLS'], 'a') as handle:
    handle.write(json.dumps(['verifier', *sys.argv[1:]]) + '\\n')
""")

    def tearDown(self):
        self.temporary.cleanup()

    def fake(self, name, body):
        path = self.root / name
        path.write_text("#!/usr/bin/env python3\n" + body)
        path.chmod(0o755)
        return path

    def run_audit(self, today):
        return subprocess.run(
            [
                AUDITOR,
                "--config", self.config,
                "--start", "2026-07-22",
                "--collector", self.collector,
                "--verifier", self.verifier,
            ],
            env={
                **os.environ,
                "AI_TOKEN_SOAK_AUDIT_TODAY": today,
                "AUDIT_CALLS": str(self.calls),
            },
            text=True,
            capture_output=True,
        )

    def test_cumulative_audit_collects_live_and_requires_post_day_anchors(self):
        result = self.run_audit("2026-07-24")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls[0][0:2], ["collector", "--live-fleet"])
        output = pathlib.Path(calls[0][calls[0].index("--output") + 1])
        self.assertFalse(output.exists())
        verifier = calls[1]
        self.assertEqual(verifier[verifier.index("--days") + 1], "2")
        self.assertEqual(verifier[verifier.index("--through") + 1], "2026-07-23")
        self.assertEqual(verifier[verifier.index("--profile") + 1], "canary-fixture")
        self.assertEqual(verifier[verifier.index("--expect-commit") + 1], "a" * 40)
        self.assertEqual(
            [verifier[index + 1] for index, value in enumerate(verifier) if value == "--require"],
            ["farol:leader", "agent-1:follower", "Kelvins-MacBook-Air:follower"],
        )

    def test_activation_day_is_a_noop(self):
        result = self.run_audit("2026-07-22")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no completed soak day", result.stdout)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
