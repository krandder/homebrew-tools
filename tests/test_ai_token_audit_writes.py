import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"


class AuditWriteSafetyTest(unittest.TestCase):
    def test_event_log_never_follows_a_destination_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            home = root / "home"
            binary = root / "bin"
            home.mkdir()
            binary.mkdir()
            curl = binary / "curl"
            curl.write_text("#!/bin/sh\nexit 0\n")
            curl.chmod(0o755)
            config = home / ".claude-token" / "config"
            config.parent.mkdir()
            config.write_text(
                "user=fixture\nurl=https://vault.invalid\ntoken=fixture-token\nmode=follower\n"
            )
            logs = home / "logs"
            logs.mkdir()
            victim = root / "unrelated-event-target"
            victim.write_text("do-not-touch\n")
            events = logs / "events.jsonl"
            events.symlink_to(victim)
            before = victim.read_bytes()
            environment = {
                **os.environ,
                "HOME": str(home),
                "AI_TOKEN_REAL_HOME": str(home),
                "AI_TOKEN_LOG_DIR": str(logs),
                "PATH": f"{binary}:/usr/bin:/bin",
            }

            result = subprocess.run(
                [AI_TOKEN, "claude", "heartbeat", "test"],
                env=environment,
                text=True,
                capture_output=True,
                timeout=15,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(victim.read_bytes(), before)
            self.assertFalse(events.is_symlink())
            self.assertIn('"event":"heartbeat"', events.read_text())
            self.assertEqual(events.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
