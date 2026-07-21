import pathlib
import stat
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = {
    "deploy/canary/farol/ai-token-canary-vault.service": 0o644,
    "deploy/canary/farol/ai-token-canary.service": 0o644,
    "deploy/canary/farol/ai-token-canary.timer": 0o644,
    "deploy/canary/farol/ai-token-canary-alert@.service": 0o644,
    "deploy/canary/farol/ai-token-soak-audit.service": 0o644,
    "deploy/canary/farol/ai-token-soak-audit.timer": 0o644,
    "deploy/canary/agent-1/ai-token-canary.service": 0o644,
    "deploy/canary/agent-1/ai-token-canary.timer": 0o644,
    "deploy/canary/agent-1/ai-token-canary-alert@.service": 0o644,
    "deploy/canary/macos/com.futarchy.ai-token-canary-dispatch.plist": 0o644,
    "deploy/canary/macos/run-as-ai-token-canary.expect": 0o755,
    "deploy/canary/macos/run-live": 0o755,
    "deploy/canary/macos/run-scheduled": 0o755,
}


class CanaryDeploymentAssetsTest(unittest.TestCase):
    def test_scheduler_assets_are_immutable_release_payloads(self):
        builder = (ROOT / "tools" / "build-release").read_text()
        for relative, mode in ASSETS.items():
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertIn(f'"{relative}"', builder)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode, relative)

    def test_linux_units_pin_the_runner_and_isolated_config(self):
        cases = {
            "farol": ("/home/kelvin/.ai-token-canary", "00/2:00:00 UTC", "leader", "Two-hour"),
            "agent-1": ("/home/kas/.ai-token-canary", "04:10:00 UTC", "follower", "Daily"),
        }
        for host, (home, schedule, role, cadence) in cases.items():
            with self.subTest(host=host):
                unit = (ROOT / "deploy" / "canary" / host / "ai-token-canary.service").read_text()
                timer = (ROOT / "deploy" / "canary" / host / "ai-token-canary.timer").read_text()
                self.assertIn(f"Description={cadence} ai-token {role} lifecycle canary", unit)
                self.assertIn(
                    f"ExecStart={home}/release/current/tools/run-live-canary --config {home}/canary.json --live",
                    unit,
                )
                self.assertIn("Environment=AI_TOKEN_CANARY_TRIGGER=scheduled", unit)
                self.assertIn(f"OnCalendar=*-*-* {schedule}", timer)
                self.assertIn("Persistent=true", timer)

    def test_isolated_vault_alerts_enter_the_canonical_incident_pipeline(self):
        unit = (ROOT / "deploy/canary/farol/ai-token-canary-vault.service").read_text()
        self.assertIn("Environment=HOME=/home/kelvin/.ai-token-canary", unit)
        self.assertIn("/home/kelvin/.npm-global/bin", unit)
        self.assertIn(
            "Environment=AI_VAULT_INCIDENT_BIN=/home/kelvin/.openclaw/workspace/scripts/incident.py",
            unit,
        )
        self.assertIn(
            "Environment=OPENCLAW_STATE_DIR=/home/kelvin/.openclaw/workspace",
            unit,
        )
        self.assertIn(
            "ExecStart=/home/kelvin/.ai-token-canary/release/current/ai-vault-http",
            unit,
        )

    def test_farol_on_failure_uses_the_canonical_incident_category(self):
        unit = (ROOT / "deploy/canary/farol/ai-token-canary-alert@.service").read_text()
        self.assertIn("--category health-check-fail", unit)
        self.assertNotIn("--category auth-credential", unit)

    def test_farol_audits_missing_scheduled_evidence_after_daily_anchors(self):
        service = (ROOT / "deploy/canary/farol/ai-token-soak-audit.service").read_text()
        timer = (ROOT / "deploy/canary/farol/ai-token-soak-audit.timer").read_text()
        builder = (ROOT / "tools/build-release").read_text()
        self.assertIn('"tools/audit-live-soak"', builder)
        self.assertIn('"tools/collect-live-soak"', builder)
        self.assertIn("OnFailure=ai-token-canary-alert@%n.service", service)
        self.assertIn(
            "ExecStart=/home/kelvin/.ai-token-canary/release/current/tools/audit-live-soak "
            "--config /home/kelvin/.ai-token-canary/canary.json --start 2026-07-22",
            service,
        )
        self.assertIn("OnCalendar=*-*-* 04:40:00 UTC", timer)
        self.assertIn("Persistent=true", timer)

    def test_macos_dispatch_switches_uid_and_unlocks_only_canary_keychain(self):
        root = ROOT / "deploy" / "canary" / "macos"
        dispatcher = (root / "com.futarchy.ai-token-canary-dispatch.plist").read_text()
        switch = (root / "run-as-ai-token-canary.expect").read_text()
        scheduled = (root / "run-scheduled").read_text()
        live = (root / "run-live").read_text()

        self.assertIn("/Users/Shared/run-as-ai-token-canary.expect", dispatcher)
        self.assertIn("/Users/ai-token-canary/.config/ai-token-canary/run-scheduled", dispatcher)
        self.assertIn('password_file "/Users/kas/.config/ai-token-canary/bootstrap-password"', switch)
        self.assertIn("spawn /usr/bin/su ai-token-canary -c", switch)
        self.assertNotIn("su - ai-token-canary", switch)
        self.assertIn('enabled="$home/.config/ai-token-canary/enabled"', scheduled)
        self.assertIn('[ -f "$enabled" ] || exit 0', scheduled)
        self.assertIn('export AI_TOKEN_CANARY_TRIGGER=scheduled', scheduled)
        self.assertIn('keychain="$home/Library/Keychains/ai-token-canary.keychain-db"', live)
        self.assertIn("security unlock-keychain", live)
        self.assertIn("current/tools/run-live-canary", live)


if __name__ == "__main__":
    unittest.main()
