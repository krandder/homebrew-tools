import importlib.machinery
import importlib.util
import json
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_VAULT_HTTP = ROOT / "ai-vault-http"


class VaultHttpTest(unittest.TestCase):
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
            with mock.patch.dict(os.environ, env, clear=False):
                loader = importlib.machinery.SourceFileLoader("ai_vault_http_test_module", str(AI_VAULT_HTTP))
                spec = importlib.util.spec_from_loader(loader.name, loader)
                module = importlib.util.module_from_spec(spec)
                loader.exec_module(module)
                access, ttl = module.broker_refresh("fixture")

            self.assertEqual(access, "fresh-access")
            self.assertEqual(ttl, 600)


if __name__ == "__main__":
    unittest.main()
