#!/usr/bin/env python3
"""proxy-install must pair the any-proxy with its watchdog, or refuse.

The 2026-07-22 wedge's deepest defect was that a proxy could exist with no
semantic health supervision at all. These tests pin the anti-blindness
invariant for `ai-token claude proxy-install`:

* the install writes BOTH the any-proxy unit and its watchdog
  (claude-any-proxy-watchdog.service Type=oneshot +
  claude-any-proxy-watchdog.timer on a 30s cadence) and enables the timer;
* the watchdog's ExecStart runs bin/proxy-watchdog.sh --once against the
  matching http://127.0.0.1:7800/healthz;
* when bin/proxy-watchdog.sh is missing the install warns loudly and exits 3
  — refusing a partial install — leaving no units behind and systemd
  untouched;
* re-install is idempotent (no duplicated or drifting units).

Fully offline: systemctl is a PATH mock that only records invocations.
"""

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"
UNIT_NAMES = (
    "claude-token-proxy.service",
    "claude-any-proxy.service",
    "claude-any-proxy-watchdog.service",
    "claude-any-proxy-watchdog.timer",
)


class ProxyInstallPairingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = pathlib.Path(self.temporary.name)
        self.home = base / "home"
        self.home.mkdir()
        self.mockbin = base / "mockbin"
        self.mockbin.mkdir()
        self.systemctl_log = base / "systemctl.log"
        systemctl = self.mockbin / "systemctl"
        systemctl.write_text(
            "#!/usr/bin/env bash\n"
            'printf "%s\\n" "$*" >> "$SYSTEMCTL_LOG"\n'
        )
        systemctl.chmod(0o755)

    def env(self):
        return {
            **os.environ,
            "HOME": str(self.home),
            "AI_TOKEN_REAL_HOME": str(self.home),
            "AI_TOKEN_LOG_DIR": str(self.home / "logs"),
            "CLAUDE_PROXY_RUNTIME": "/bin/true",
            "SYSTEMCTL_LOG": str(self.systemctl_log),
            "PATH": f"{self.mockbin}:/usr/bin:/bin",
        }

    def unit_dir(self):
        return self.home / ".config" / "systemd" / "user"

    def units_on_disk(self):
        directory = self.unit_dir()
        if not directory.is_dir():
            return {}
        return {
            path.name: path.read_bytes()
            for path in directory.iterdir()
            if path.suffix in (".service", ".timer")
        }

    def install(self, script=AI_TOKEN):
        return subprocess.run(
            [str(script), "claude", "proxy-install"],
            env=self.env(), text=True, capture_output=True, timeout=15,
        )

    def test_install_pairs_the_proxy_with_its_watchdog(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)

        units = self.units_on_disk()
        for name in UNIT_NAMES:
            self.assertIn(name, units, f"proxy-install must emit {name}")

        proxy = units["claude-any-proxy.service"].decode()
        self.assertIn("any-proxy.mjs", proxy)

        watchdog = units["claude-any-proxy-watchdog.service"].decode()
        self.assertIn("Type=oneshot", watchdog)
        self.assertIn("bin/proxy-watchdog.sh", watchdog)
        self.assertIn(
            "--once claude-any-proxy http://127.0.0.1:7800/healthz",
            watchdog,
            "watchdog ExecStart must probe the matching /healthz URL",
        )

        timer = units["claude-any-proxy-watchdog.timer"].decode()
        self.assertIn("OnBootSec=30", timer)
        self.assertIn("OnUnitActiveSec=30", timer)

        calls = self.systemctl_log.read_text()
        self.assertIn("enable --now claude-any-proxy-watchdog.timer", calls)

    def test_missing_watchdog_refuses_partial_install(self):
        # An ai-token outside the repo has no bin/proxy-watchdog.sh next to
        # it: the install must refuse loudly (exit 3) instead of deploying an
        # unsupervised proxy — the refusal IS the anti-blindness invariant.
        fake_repo = pathlib.Path(self.temporary.name) / "fake-repo"
        fake_repo.mkdir()
        script = fake_repo / "ai-token"
        shutil.copy(AI_TOKEN, script)
        script.chmod(0o755)

        result = self.install(script=script)

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("proxy-watchdog.sh", result.stderr)
        self.assertEqual(
            {}, self.units_on_disk(),
            "refused install must leave no half-installed proxy unit behind",
        )
        self.assertFalse(
            self.systemctl_log.exists(),
            "refused install must not touch systemd at all",
        )

    def test_reinstall_is_idempotent(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        snapshot = self.units_on_disk()
        self.assertEqual(len(UNIT_NAMES), len(snapshot))

        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(
            snapshot, self.units_on_disk(),
            "re-install duplicated or rewrote units",
        )


if __name__ == "__main__":
    unittest.main()
