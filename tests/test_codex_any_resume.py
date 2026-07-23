#!/usr/bin/env python3
"""Hermetic regression tests for codex-any's dedicated home."""

import base64
import json
import os
import socketserver
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "codex-any"


def token():
    payload = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + 3600}).encode()).rstrip(b"=")
    return f"e30.{payload.decode()}.sig"


class Proxy:
    def __enter__(self):
        self.server = socketserver.TCPServer(("127.0.0.1", 0), socketserver.BaseRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class CodexAnyResumeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        auth = self.home / ".codex-profiles/test/.codex/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text(json.dumps({"tokens": {"access_token": token()}}))
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        codex = bin_dir / "codex"
        codex.write_text(
            "#!/usr/bin/env bash\n"
            "find \"$CODEX_HOME/sessions\" -name '*.jsonl' -print -quit > \"$HOME/codex.session-at-exec\"\n"
            "printf '%s\\n' \"$*\" > \"$HOME/codex.argv\"\n"
        )
        codex.chmod(codex.stat().st_mode | stat.S_IXUSR)
        self.wrapper = self.home / "codex-any"
        self.wrapper.write_text(WRAPPER.read_text())
        self.wrapper.chmod(self.wrapper.stat().st_mode | stat.S_IXUSR)
        self.env = {"HOME": str(self.home), "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FLEET_ACTOR": "cao-ops-ci"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_wrapper(self, *args):
        return subprocess.run([self.wrapper, *args], env=self.env, text=True, capture_output=True)

    def use_proxy(self, proxy):
        self.wrapper.write_text(WRAPPER.read_text().replace("7810", str(proxy.server.server_address[1])))

    def test_resume_seeds_rollout_before_exec(self):
        rollout = self.home / ".codex/sessions/2026/07/14/rollout-abc123.jsonl"
        rollout.parent.mkdir(parents=True)
        rollout.write_text('{"type":"session_meta","payload":{}}\n')
        with Proxy() as proxy:
            self.use_proxy(proxy)
            result = self.run_wrapper("resume", "abc123")
        self.assertEqual(result.returncode, 0, result.stderr)
        seeded = self.home / ".codex-any/sessions/2026/07/14/rollout-abc123.jsonl"
        self.assertTrue(seeded.is_file())
        self.assertEqual((self.home / "codex.argv").read_text().strip(), "resume abc123")
        self.assertEqual((self.home / "codex.session-at-exec").read_text().strip(), str(seeded))

    def test_concurrent_first_runs_succeed(self):
        with Proxy() as proxy:
            self.use_proxy(proxy)
            first = subprocess.Popen([self.wrapper, "exec", "one"], env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            second = subprocess.Popen([self.wrapper, "exec", "two"], env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            first_out, first_err = first.communicate(timeout=10)
            second_out, second_err = second.communicate(timeout=10)
        self.assertEqual(first.returncode, 0, first_err)
        self.assertEqual(second.returncode, 0, second_err)
        self.assertEqual(json.loads((self.home / ".codex-any/auth.json").read_text())["tokens"]["refresh_token"], "sentinel-follower")
        config = (self.home / ".codex-any/config.toml").read_text()
        self.assertIn('model = "gpt-5.6-terra"', config)
        self.assertIn("model_provider", config)
        self.assertIn(
            'env_http_headers = { "X-Futarchy-Agent" = "FUTARCHY_AGENT_NAME" }',
            config)


if __name__ == "__main__":
    unittest.main()
