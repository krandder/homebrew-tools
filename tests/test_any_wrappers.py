#!/usr/bin/env python3
"""Hermetic tests for the claude-any wrapper's env hygiene and dispatch.

The wrapper runs under `env -i` with stub claude.real / claude / ai-any that
record their environment and argv. Asserts: inherited CLAUDE* noise
(CLAUDECODE, CLAUDE_CODE_SSE_PORT) is stripped; the provider-auth allowlist
(CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_SKIP_*_AUTH) survives; the proxy-down
path execs ai-any; the proxy-up path exports
ANTHROPIC_BASE_URL=http://127.0.0.1:7800 and ANTHROPIC_AUTH_TOKEN=token-proxy-managed
and prefers $HOME/bin/claude.real.

The tests select a private loopback port through AI_ANY_PROXY_PORT, so neither
path depends on a real proxy. No upstream traffic: the wrapper only opens and
closes the probe connection before exec, and the stubs never speak to it.
"""

import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "claude-any"

CAPTURE_STUB = """#!/usr/bin/env bash
{ env
  printf '__ARGV__'
  printf ' %s' "$@"
  printf '\\n'
} > "$CAP_DIR/__NAME__.capture"
"""

PROVIDER_ALLOWLIST = {
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_SKIP_BEDROCK_AUTH", "CLAUDE_CODE_SKIP_VERTEX_AUTH",
    "CLAUDE_CODE_SKIP_FOUNDRY_AUTH",
}
# exported by claude-any itself, not inherited noise
WRAPPER_OWN_EXPORTS = {"CLAUDE_CONFIG_DIR"}


class ClaudeAnyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.stubbin = base / "bin"
        self.cap = base / "cap"
        (self.home / "bin").mkdir(parents=True)
        self.stubbin.mkdir()
        self.cap.mkdir()
        for path, name in ((self.home / "bin" / "claude.real", "claude.real"),
                           (self.stubbin / "claude", "claude"),
                           (self.stubbin / "ai-any", "ai-any")):
            path.write_text(CAPTURE_STUB.replace("__NAME__", name))
            path.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_wrapper(self, port):
        cmd = [
            "env", "-i",
            f"HOME={self.home}",
            f"PATH={self.stubbin}:/usr/bin:/bin",
            f"CAP_DIR={self.cap}",
            f"AI_ANY_PROXY_PORT={port}",
            "FLEET_ACTOR=cao-mnx-mm",
            "CLAUDECODE=1",
            "CLAUDE_CODE_SSE_PORT=9",
            "CLAUDE_CODE_USE_BEDROCK=1",
            "CLAUDE_CODE_SKIP_VERTEX_AUTH=1",
            "bash", str(WRAPPER), "--version",
        ]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0,
                         f"claude-any failed: rc={result.returncode} stderr={result.stderr}")
        return result

    def captured(self, name):
        lines = (self.cap / f"{name}.capture").read_text().splitlines()
        env = dict(line.split("=", 1) for line in lines if not line.startswith("__ARGV__"))
        argv = [l.split()[1:] for l in lines if l.startswith("__ARGV__")][0]
        return env, argv

    def assert_env_hygiene(self, env):
        allowed = PROVIDER_ALLOWLIST | WRAPPER_OWN_EXPORTS
        leaked = sorted(k for k in env if k.startswith("CLAUDE") and k not in allowed)
        self.assertEqual(leaked, [], "inherited CLAUDE* noise must be stripped")
        self.assertEqual(env.get("CLAUDE_CODE_USE_BEDROCK"), "1",
                         "provider-auth allowlist must survive")
        self.assertEqual(env.get("CLAUDE_CODE_SKIP_VERTEX_AUTH"), "1")

    def test_proxy_up_path(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            self.run_wrapper(port)
        finally:
            listener.close()
        env, argv = self.captured("claude.real")
        self.assertEqual(argv, ["--version"])
        self.assertEqual(env.get("ANTHROPIC_BASE_URL"), f"http://127.0.0.1:{port}")
        self.assertEqual(env.get("ANTHROPIC_AUTH_TOKEN"),
                         "token-proxy-managed:cao-mnx-mm")
        self.assertEqual(env.get("CLAUDE_CONFIG_DIR"), f"{self.home}/.claude")
        self.assert_env_hygiene(env)

    def test_proxy_down_falls_back_to_ai_any(self):
        unused = socket.socket()
        unused.bind(("127.0.0.1", 0))
        port = unused.getsockname()[1]
        unused.close()
        self.run_wrapper(port)
        env, argv = self.captured("ai-any")
        self.assertEqual(argv, ["--version"])
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assert_env_hygiene(env)


if __name__ == "__main__":
    unittest.main()
