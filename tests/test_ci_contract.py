import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class CiContractTest(unittest.TestCase):
    def test_release_gate_is_blocking_scheduled_and_retains_evidence(self):
        workflow = WORKFLOW.read_text()
        for trigger in ("push:", "pull_request:", "workflow_dispatch:", "schedule:"):
            self.assertIn(trigger, workflow)
        self.assertIn('cron: "17 3 * * *"', workflow)
        self.assertEqual(workflow.count("tools/build-release"), 1)
        self.assertIn("actions/checkout@v6", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("tools/verify-tdd-history", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("actions/upload-artifact@v7", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("retention-days: 30", workflow)
        self.assertNotIn("continue-on-error", workflow)


if __name__ == "__main__":
    unittest.main()
