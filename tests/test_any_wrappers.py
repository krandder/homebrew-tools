#!/usr/bin/env python3
"""Hermetic tests for the claude-any wrapper's env hygiene and dispatch.

The wrapper runs under `env -i` with stub claude.real / claude / ai-any that
record their environment and argv. Asserts: inherited CLAUDE* noise
(CLAUDECODE, CLAUDE_CODE_SSE_PORT) is stripped; the provider-auth allowlist
(CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_SKIP_*_AUTH) survives; the proxy-down
path execs ai-any; the proxy-up path exports
ANTHROPIC_BASE_URL=http://127.0.0.1:7800 and ANTHROPIC_AUTH_TOKEN=token-proxy-managed
and prefers $HOME/bin/claude.real.

The 127.0.0.1:7800 probe is environment-dependent: on a host already running
the real any-proxy the port is open, so the proxy-down path is exercised
inside an unprivileged network namespace (unshare -Urn, where nothing listens
on 7800); the proxy-up path uses the real listener or a throwaway socket
bound by the test itself. No upstream traffic: the wrapper only opens and
closes the probe connection before exec, and the stubs never speak to it.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "claude-any"
ANY_PORT = 7800

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


def port_open(port=ANY_PORT):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def userns_net_available():
    if not shutil.which("unshare"):
        return False
    return subprocess.run(["unshare", "-Urn", "true"], capture_output=True).returncode == 0


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

    def run_wrapper(self, netns=False):
        cmd = ["unshare", "-Urn"] if netns else []
        cmd += [
            "env", "-i",
            f"HOME={self.home}",
            f"PATH={self.stubbin}:/usr/bin:/bin",
            f"CAP_DIR={self.cap}",
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
        listener = None
        if not port_open():
            listener = socket.socket()
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", ANY_PORT))
            listener.listen(1)
        try:
            self.run_wrapper()
        finally:
            if listener is not None:
                listener.close()
        env, argv = self.captured("claude.real")
        self.assertEqual(argv, ["--version"])
        self.assertEqual(env.get("ANTHROPIC_BASE_URL"), f"http://127.0.0.1:{ANY_PORT}")
        self.assertEqual(env.get("ANTHROPIC_AUTH_TOKEN"), "token-proxy-managed")
        self.assertEqual(env.get("CLAUDE_CONFIG_DIR"), f"{self.home}/.claude")
        self.assert_env_hygiene(env)

    def test_proxy_down_falls_back_to_ai_any(self):
        netns = False
        if port_open():
            if not userns_net_available():
                self.skipTest("127.0.0.1:7800 is occupied and unshare -Urn is unavailable")
            netns = True
        self.run_wrapper(netns=netns)
        env, argv = self.captured("ai-any")
        self.assertEqual(argv, ["--version"])
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assert_env_hygiene(env)


if __name__ == "__main__":
    unittest.main()
