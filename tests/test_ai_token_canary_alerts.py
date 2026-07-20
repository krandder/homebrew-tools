import hashlib
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from support import MockOAuthServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORTER = ROOT / "tools" / "report-canary-failure"
VAULT_HTTP = ROOT / "ai-vault-http"
COMMIT = "a" * 40


class CanaryAlertTest(unittest.TestCase):
    def test_follower_reporter_posts_only_sanitized_failure_metadata(self):
        with tempfile.TemporaryDirectory() as temporary, MockOAuthServer() as server:
            root = pathlib.Path(temporary)
            home = root / "home"
            evidence = root / "evidence"
            (home / ".claude-token").mkdir(parents=True)
            evidence.mkdir()
            base_url = f"http://127.0.0.1:{server.server.server_port}"
            (home / ".claude-token" / "config").write_text(
                f"url={base_url}\ntoken=alert-token\n"
            )
            config = root / "canary.json"
            config.write_text(json.dumps({
                "schema": 1,
                "kind": "claude",
                "profile": "canary-fixture",
                "non_human": True,
                "role": "follower",
                "home": str(home),
                "release_root": str(root / "release"),
                "expect_commit": COMMIT,
                "evidence_dir": str(evidence),
            }))
            config.chmod(0o600)
            failure = evidence / "failure.json"
            failure.write_text(json.dumps({
                "status": "failed",
                "steps": [{"name": "pull", "returncode": 7}],
                "secret": "MUST_NOT_LEAK",
            }))

            result = subprocess.run(
                [REPORTER, "--config", config],
                env={**os.environ, "HOME": str(home), "AI_TOKEN_CANARY_HOST": "agent-1"},
                text=True,
                capture_output=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(server.requests), 1)
            method, path, headers, raw = server.requests[0]
            self.assertEqual((method, path), ("POST", "/canary-alert"))
            self.assertEqual(headers["Authorization"], "Bearer alert-token")
            payload = json.loads(raw)
            self.assertEqual(payload, {
                "schema": 1,
                "host": "agent-1",
                "role": "follower",
                "profile": "canary-fixture",
                "expect_commit": COMMIT,
                "phase": "pull",
                "returncode": 7,
                "evidence": "failure.json",
            })
            self.assertNotIn("MUST_NOT_LEAK", raw.decode())

    def test_authenticated_vault_route_rejects_human_profiles_and_files_incident(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            token = "alert-token"
            (vault / "tokens.json").write_text(json.dumps({
                hashlib.sha256(token.encode()).hexdigest(): "follower-a"
            }))
            calls = root / "incident-calls.jsonl"
            incident = root / "incident"
            incident.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "with open(os.environ['INCIDENT_CALLS'], 'a') as handle:\n"
                "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            )
            incident.chmod(0o755)
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            environment = {
                **os.environ,
                "CODEX_VAULT_DIR": str(vault),
                "CODEX_VAULT_LISTEN": f"127.0.0.1:{port}",
                "AI_VAULT_INCIDENT_BIN": str(incident),
                "INCIDENT_CALLS": str(calls),
            }
            server = subprocess.Popen(
                [VAULT_HTTP], env=environment, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, text=True,
            )
            try:
                health = f"http://127.0.0.1:{port}/healthz"
                for _ in range(100):
                    try:
                        urllib.request.urlopen(health, timeout=0.2).read()
                        break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.02)
                else:
                    self.fail("ai-vault-http did not start")

                alert = {
                    "schema": 1,
                    "host": "agent-1",
                    "role": "follower",
                    "profile": "canary-fixture",
                    "expect_commit": COMMIT,
                    "phase": "pull",
                    "returncode": 7,
                    "evidence": "failure.json",
                }
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/canary-alert",
                    data=json.dumps(alert).encode(),
                    headers={"Authorization": f"Bearer {token}"},
                    method="POST",
                )
                self.assertEqual(urllib.request.urlopen(request, timeout=2).status, 200)
                stored = list((vault / "canary-alerts" / "follower-a").glob("*.json"))
                self.assertEqual(len(stored), 1)
                self.assertEqual(json.loads(stored[0].read_text()), {**alert, "vault_user": "follower-a"})
                self.assertTrue(calls.is_file())
                self.assertIn("ai-token canary failed on agent-1", calls.read_text())

                alert["profile"] = "human-profile"
                rejected = urllib.request.Request(
                    f"http://127.0.0.1:{port}/canary-alert",
                    data=json.dumps(alert).encode(),
                    headers={"Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(rejected, timeout=2)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(len(list((vault / "canary-alerts" / "follower-a").glob("*.json"))), 1)
            finally:
                server.terminate()
                server.wait(timeout=3)

    def test_release_contains_follower_failure_hooks(self):
        builder = (ROOT / "tools" / "build-release").read_text()
        expected = (
            "tools/report-canary-failure",
            "deploy/canary/agent-1/ai-token-canary-alert@.service",
        )
        for relative in expected:
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertIn(f'"{relative}"', builder)

        agent = (ROOT / "deploy/canary/agent-1/ai-token-canary.service").read_text()
        mac = (ROOT / "deploy/canary/macos/run-scheduled").read_text()
        self.assertIn("OnFailure=ai-token-canary-alert@%n.service", agent)
        self.assertIn("report-canary-failure", mac)
        self.assertIn("exit $status", mac)


if __name__ == "__main__":
    unittest.main()
