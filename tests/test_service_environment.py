import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"


class ServiceEnvironmentTest(unittest.TestCase):
    def test_proxy_unit_pins_the_invoked_canonical_binary_and_service_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = pathlib.Path(directory)
            binary = home / "bin"
            binary.mkdir()
            calls = home / "systemctl.calls"
            systemctl = binary / "systemctl"
            systemctl.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {calls}\n")
            systemctl.chmod(0o755)
            stale = binary / "claude-token"
            stale.write_text("#!/usr/bin/env bash\necho stale-writer\n")
            stale.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(home),
                "AI_TOKEN_REAL_HOME": str(home),
                "PATH": f"{binary}:/usr/bin:/bin",
            }
            result = subprocess.run(
                [AI_TOKEN, "claude", "proxy-install"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            unit = (home / ".config" / "systemd" / "user" / "claude-token-proxy.service").read_text()
            self.assertIn(f"ExecStart={AI_TOKEN} claude proxy", unit)
            self.assertIn(f"Environment=PATH={ROOT}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", unit)
            self.assertNotIn(str(stale), unit)
            self.assertIn("daemon-reload", calls.read_text())


if __name__ == "__main__":
    unittest.main()
