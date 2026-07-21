import importlib.machinery
import importlib.util
import hashlib
import http.client
import http.server
import json
import os
import pathlib
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_VAULT_HTTP = ROOT / "ai-vault-http"


class VaultHttpTest(unittest.TestCase):
    @staticmethod
    def load_module(name, environment):
        with mock.patch.dict(os.environ, environment, clear=False):
            loader = importlib.machinery.SourceFileLoader(name, str(AI_VAULT_HTTP))
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
        return module

    def post(self, module, vault, path, body):
        token = "fixture-token"
        (vault / "tokens.json").write_text(json.dumps({
            hashlib.sha256(token.encode()).hexdigest(): "fixture-user",
        }))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=5,
            )
            connection.request(
                "POST", path, body=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            payload = response.read()
            connection.close()
            return response.status, payload
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_broker_success_returns_the_current_follower_access_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            shared = home / "shared" / "claude-tokens" / "fixture.json"
            shared.parent.mkdir(parents=True)
            shared.write_text(json.dumps({
                "claudeAiOauth": {
                    "accessToken": "fresh-access",
                    "refreshToken": "__follower_no_refresh__",
                    "expiresAt": (int(time.time()) + 3600) * 1000,
                }
            }))
            env = {
                "HOME": str(home),
                "CODEX_VAULT_DIR": str(home / "vault"),
                "AI_TOKEN_BIN": "/bin/true",
                "AI_TOKEN_TEST_NOW": str(int(time.time()) + 3000),
            }
            module = self.load_module("ai_vault_http_test_module", env)
            with mock.patch.dict(os.environ, env, clear=False):
                access, ttl = module.broker_refresh("fixture")

            self.assertEqual(access, "fresh-access")
            self.assertEqual(ttl, 600)

    def test_http_event_log_never_follows_a_destination_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            vault = home / "vault"
            vault.mkdir()
            victim = home / "unrelated-http-event-target"
            victim.write_text("do-not-touch\n")
            events = vault / "http-events.jsonl"
            events.symlink_to(victim)
            before = victim.read_bytes()
            module = self.load_module(
                "ai_vault_http_event_test_module",
                {"HOME": str(home), "CODEX_VAULT_DIR": str(vault)},
            )

            module.server_event("test-event", "fixture", "claude:fixture", "ok", "safe")

            self.assertEqual(victim.read_bytes(), before)
            self.assertFalse(events.is_symlink())
            record = json.loads(events.read_text())
            self.assertEqual(record["event"], "test-event")
            self.assertEqual(events.stat().st_mode & 0o777, 0o600)

    def test_heartbeat_snapshot_never_follows_a_destination_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            vault = home / "vault"
            heartbeat_dir = vault / "client-heartbeats" / "fixture-user"
            heartbeat_dir.mkdir(parents=True)
            victim = home / "unrelated-heartbeat-target"
            victim.write_text("do-not-touch\n")
            heartbeat = heartbeat_dir / "claude-token-fixture-host.json"
            heartbeat.symlink_to(victim)
            before = victim.read_bytes()
            module = self.load_module(
                "ai_vault_http_heartbeat_test_module",
                {"HOME": str(home), "CODEX_VAULT_DIR": str(vault)},
            )
            body = json.dumps({
                "host": "fixture-host",
                "version": "3.2.0",
                "profile": "canary-fixture",
                "mode": "follower",
                "status": "ok",
            })

            status, _payload = self.post(module, vault, "/heartbeat/claude-token", body)

            self.assertEqual(status, 200)
            self.assertEqual(victim.read_bytes(), before)
            self.assertFalse(heartbeat.is_symlink())
            record = json.loads(heartbeat.read_text())
            self.assertEqual(record["vault_user"], "fixture-user")
            self.assertEqual(heartbeat.stat().st_mode & 0o777, 0o600)

    def test_http_state_snapshots_do_not_use_direct_write_text(self):
        if "out.write_text" in AI_VAULT_HTTP.read_text():
            self.fail("direct HTTP state snapshot write remains")


if __name__ == "__main__":
    unittest.main()
