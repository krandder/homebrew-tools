import datetime
import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify-live-soak"
COMMIT = "a" * 40
PROFILE = "canary-fixture"
RELEASE = f"{COMMIT[:12]}-{'b' * 12}"


class SoakEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.counter = 0
        self.latest = {}

    def tearDown(self):
        self.temporary.cleanup()

    def write_record(
        self, day, host, role, *, status="ok", commit=COMMIT, steps=None,
        state_before=None, state_after=None, trigger="scheduled",
    ):
        self.counter += 1
        if steps is None:
            names = ["verify-release", "publish"] if role == "leader" else [
                "verify-release", "pull", "check",
            ]
            steps = [{"name": name, "returncode": 0} for name in names]
        previous = self.latest.get((host, role))
        previous_evidence = None if previous is None else {
            "name": previous.name,
            "sha256": hashlib.sha256(previous.read_bytes()).hexdigest(),
        }
        record = {
            "schema": 3,
            "timestamp": f"{day}T12:00:00+00:00",
            "host": host,
            "kind": "claude",
            "profile": PROFILE,
            "role": role,
            "expect_commit": commit,
            "release": RELEASE,
            "status": status,
            "trigger": trigger,
            "previous_evidence": previous_evidence,
            "steps": steps,
            "state_before": state_before or {"credential": {"exists": False}},
            "state_after": state_after or {"credential": {"exists": False}},
        }
        path = self.evidence / f"{day}-{host}-{role}-{self.counter}.json"
        path.write_text(json.dumps(record))
        path.chmod(0o600)
        self.latest[(host, role)] = path
        return path

    def populate(self, start="2026-07-20", days=3, anchor=True):
        first = datetime.date.fromisoformat(start)
        for offset in range(days):
            day = str(first + datetime.timedelta(days=offset))
            before = {"credential": {
                "exists": True, "size": offset, "mtime_ns": offset,
                "ctime_ns": offset, "inode": 1, "mode": "0600",
            }}
            after = {"credential": {
                "exists": True, "size": offset + 1, "mtime_ns": offset + 1,
                "ctime_ns": offset + 1, "inode": 1, "mode": "0600",
            }}
            self.write_record(day, "farol", "leader", state_before=before, state_after=after)
            self.write_record(day, "agent-1", "follower", state_before=before, state_after=after)
        if anchor:
            day = str(first + datetime.timedelta(days=days))
            before = {"credential": {
                "exists": True, "size": days, "mtime_ns": days,
                "ctime_ns": days, "inode": 1, "mode": "0600",
            }}
            after = {"credential": {
                "exists": True, "size": days + 1, "mtime_ns": days + 1,
                "ctime_ns": days + 1, "inode": 1, "mode": "0600",
            }}
            self.write_record(day, "farol", "leader", state_before=before, state_after=after)
            self.write_record(day, "agent-1", "follower", state_before=before, state_after=after)

    def run_verifier(self, *, days="3", through="2026-07-22"):
        command = [
            VERIFIER,
            "--evidence-dir", self.evidence,
            "--profile", PROFILE,
            "--expect-commit", COMMIT,
            "--through", through,
            "--require", "farol:leader",
            "--require", "agent-1:follower",
        ]
        if days is not None:
            command.extend(["--days", days])
        return subprocess.run(command, text=True, capture_output=True, timeout=10)

    def test_complete_consecutive_cross_host_soak_passes(self):
        self.populate()
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["from"], "2026-07-20")
        self.assertEqual(report["through"], "2026-07-22")
        self.assertEqual(report["days"], 3)
        self.assertEqual(report["records"], 6)
        self.assertEqual(report["requirements"], ["agent-1:follower", "farol:leader"])

    def test_missing_host_day_fails_instead_of_shortening_the_window(self):
        self.populate()
        next(self.evidence.glob("2026-07-21-agent-1-follower-*.json")).unlink()
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("2026-07-21 agent-1:follower", result.stderr)

    def test_failed_record_cannot_be_masked_by_a_later_green_duplicate(self):
        self.populate()
        self.write_record(
            "2026-07-21",
            "agent-1",
            "follower",
            status="failed",
            steps=[
                {"name": "verify-release", "returncode": 0},
                {"name": "pull", "returncode": 7},
            ],
        )
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed canary evidence", result.stderr)

    def test_manual_success_does_not_satisfy_a_scheduled_host_day(self):
        self.write_record("2026-07-20", "farol", "leader")
        self.write_record("2026-07-20", "agent-1", "follower", trigger="manual")
        self.write_record("2026-07-21", "farol", "leader")
        self.write_record("2026-07-21", "agent-1", "follower")
        result = self.run_verifier(days="1", through="2026-07-20")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("2026-07-20 agent-1:follower", result.stderr)

    def test_omitted_failure_breaks_the_safe_evidence_chain(self):
        first = datetime.date(2026, 7, 20)
        omitted = None
        for offset in range(3):
            day = str(first + datetime.timedelta(days=offset))
            self.write_record(day, "farol", "leader")
            if offset == 1:
                omitted = self.write_record(
                    day,
                    "agent-1",
                    "follower",
                    status="failed",
                    steps=[
                        {"name": "verify-release", "returncode": 0},
                        {"name": "pull", "returncode": 7},
                    ],
                )
            self.write_record(day, "agent-1", "follower")
        self.write_record("2026-07-23", "farol", "leader")
        self.write_record("2026-07-23", "agent-1", "follower")
        omitted.unlink()
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing chained evidence", result.stderr)

    def test_post_window_anchor_is_required_for_every_scheduled_role(self):
        self.populate()
        anchor = next(self.evidence.glob("2026-07-23-agent-1-follower-*.json"))
        anchor.unlink()
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("post-window anchor", result.stderr)

    def test_mixed_commit_or_fabricated_green_steps_fail_convergence(self):
        self.populate()
        wrong_commit = next(self.evidence.glob("2026-07-21-farol-leader-*.json"))
        record = json.loads(wrong_commit.read_text())
        record["expect_commit"] = "b" * 40
        wrong_commit.write_text(json.dumps(record))
        wrong_commit.chmod(0o600)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit mismatch", result.stderr)

        record["expect_commit"] = COMMIT
        record["steps"] = [{"name": "verify-release", "returncode": 0}]
        wrong_commit.write_text(json.dumps(record))
        wrong_commit.chmod(0o600)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid successful steps", result.stderr)

    def test_mixed_immutable_release_artifact_fails_convergence(self):
        self.populate()
        wrong_release = next(self.evidence.glob("2026-07-21-agent-1-follower-*.json"))
        record = json.loads(wrong_release.read_text())
        record["release"] = f"{COMMIT[:12]}-{'c' * 12}"
        wrong_release.write_text(json.dumps(record))
        wrong_release.chmod(0o600)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release mismatch", result.stderr)

    def test_malformed_symlinked_or_permissive_evidence_fails_closed(self):
        self.populate()
        malformed = self.evidence / "malformed.json"
        malformed.write_text("not-json")
        malformed.chmod(0o600)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid evidence", result.stderr)
        malformed.unlink()

        target = self.root / "outside.json"
        target.write_text("{}")
        target.chmod(0o600)
        (self.evidence / "linked.json").symlink_to(target)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        (self.evidence / "linked.json").unlink()

        permissive = next(self.evidence.glob("*.json"))
        permissive.chmod(0o644)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mode 0600", result.stderr)

    def test_default_window_is_thirty_days(self):
        self.populate(start="2026-07-21", days=29)
        result = self.run_verifier(days=None, through="2026-08-18")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("2026-07-20", result.stderr)

    def test_soak_independently_rejects_between_run_writer_drift(self):
        self.populate()
        drifted = next(self.evidence.glob("2026-07-21-agent-1-follower-*.json"))
        record = json.loads(drifted.read_text())
        record["state_before"]["credential"]["mtime_ns"] = 999
        drifted.write_text(json.dumps(record))
        drifted.chmod(0o600)
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("writer continuity", result.stderr)


if __name__ == "__main__":
    unittest.main()
