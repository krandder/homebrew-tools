import hashlib
import datetime
import json
import os
import pathlib
import shlex
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from support import MockOAuthServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"
AI_VAULT = ROOT / "ai-vault"
AI_VAULT_HTTP = ROOT / "ai-vault-http"
SENTINEL = "__follower_no_refresh__"


class FleetLab:
    profiles = ("alpha", "beta")
    followers = ("follower-a", "follower-b")

    def __init__(self, temporary, transport, oauth):
        self.root = pathlib.Path(temporary)
        self.transport = transport
        self.oauth = oauth
        self.leader = self.root / "leader"
        self.clients = self.root / "clients"
        self.bin = self.root / "bin"
        self.bin.mkdir(parents=True)
        self.server = None
        self.base_url = ""
        self._create_leader_state()
        if transport == "http":
            self._start_http()
        else:
            self._create_ssh_transport()

    def close(self):
        if self.server is not None:
            self.server.terminate()
            try:
                self.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=5)
            self.server.stdout.close()
            self.server.stderr.close()

    @property
    def leader_env(self):
        return {
            **os.environ,
            "HOME": str(self.leader),
            "AI_TOKEN_REAL_HOME": str(self.leader),
            "CODEX_VAULT_DIR": str(self.leader / "vault"),
            "CODEX_PROFILES_DIR": str(self.leader / "codex-profiles"),
            "CLAUDE_PROFILES_DIR": str(self.leader / "claude-profiles"),
            "KIMI_PROFILES_DIR": str(self.leader / "kimi-profiles"),
            "CODEX_SHARED_DIR": str(self.leader / "shared" / "codex"),
            "CLAUDE_SHARED_DIR": str(self.leader / "shared" / "claude"),
            "KIMI_SHARED_DIR": str(self.leader / "shared" / "kimi"),
            "CODEX_TOKEN_EP": self.oauth.token_url,
            "KIMI_CODE_OAUTH_HOST": self.oauth.token_url.rsplit("/oauth/token", 1)[0],
            "AI_TOKEN_BIN": str(AI_TOKEN),
            "PATH": f"{ROOT}:/usr/bin:/bin",
        }

    def _create_leader_state(self):
        vault = self.leader / "vault"
        vault.mkdir(parents=True)
        acl_profiles = {}
        for kind in ("claude", "codex", "kimi"):
            for profile in self.profiles:
                acl_profiles[f"{kind}:{profile}"] = {
                    "owner": f"owner-{profile}",
                    "pullers": list(self.followers),
                    "kind": kind,
                }
        (vault / "acl.json").write_text(json.dumps({
            "operator": "admin",
            "admins": ["admin"],
            "profiles": acl_profiles,
        }))
        identities = ("admin", "owner-alpha", "owner-beta", *self.followers, "outsider")
        tokens = {
            hashlib.sha256(self.token(identity).encode()).hexdigest(): identity
            for identity in identities
        }
        (vault / "tokens.json").write_text(json.dumps(tokens))

    @staticmethod
    def token(identity):
        return f"test-token-{identity}"

    @staticmethod
    def _free_port():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _start_http(self):
        port = self._free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        env = {**self.leader_env, "CODEX_VAULT_LISTEN": f"127.0.0.1:{port}"}
        self.server = subprocess.Popen(
            [AI_VAULT_HTTP],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base_url}/healthz", timeout=0.2) as response:
                    if response.status == 200:
                        return
            except Exception:
                if self.server.poll() is not None:
                    break
                time.sleep(0.05)
        stderr = self.server.stderr.read() if self.server.poll() is not None else "startup timeout"
        raise AssertionError(f"ai-vault-http did not start: {stderr}")

    def _create_ssh_transport(self):
        quoted = {key: shlex.quote(value) for key, value in self.leader_env.items() if key != "CODEX_VAULT_USER"}
        exports = " ".join(f"{key}={value}" for key, value in quoted.items())
        ssh = self.bin / "ssh"
        ssh.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "command=${!#}\n"
            f"exec env {exports} CODEX_VAULT_USER=\"$TEST_VAULT_USER\" "
            f"{shlex.quote(str(AI_VAULT))} shell \"$TEST_VAULT_USER\" -- \"$command\"\n"
        )
        ssh.chmod(0o755)

    def client_env(self, machine, identity, mode="follower"):
        home = self.clients / machine
        home.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "HOME": str(home),
            "AI_TOKEN_REAL_HOME": str(home),
            "CODEX_USER": identity,
            "AI_TOKEN_MODE": mode,
            "CLAUDE_TOKEN_MODE": mode,
            "CODEX_PROFILES_DIR": str(home / "codex-profiles"),
            "CLAUDE_PROFILES_DIR": str(home / "claude-profiles"),
            "KIMI_PROFILES_DIR": str(home / "kimi-profiles"),
            "CODEX_SHARED_DIR": str(home / "shared" / "codex"),
            "CLAUDE_SHARED_DIR": str(home / "shared" / "claude"),
            "KIMI_SHARED_DIR": str(home / "shared" / "kimi"),
            "CLAUDE_PROXY_PORT_BASE": str(self._free_port()),
            "PATH": f"{self.bin}:{ROOT}:/usr/bin:/bin",
        }
        if self.transport == "http":
            env.update({
                "AI_VAULT_URL": self.base_url,
                "AI_VAULT_TOKEN": self.token(identity),
            })
        else:
            env.update({
                "AI_TOKEN_LEADER": "hermetic-leader",
                "TEST_VAULT_USER": identity,
            })
            for key in ("AI_VAULT_URL", "AI_VAULT_TOKEN", "CLAUDE_VAULT_TOKEN", "CODEX_VAULT_TOKEN"):
                env.pop(key, None)
        return home, env

    @staticmethod
    def run(kind, command, profile, env):
        return subprocess.run(
            [AI_TOKEN, kind, command, "--profile", profile],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def owner_sync(self, kind, profile, generation=1):
        home, env = self.client_env(f"owner-{kind}-{profile}", f"owner-{profile}", "owner")
        expires_seconds = int(time.time()) + 3600 + generation * 60
        access = f"{kind}-{profile}-access-{generation}"
        refresh = f"{kind}-{profile}-refresh-{generation}"
        if kind == "claude":
            path = home / ".claude" / ".credentials.json"
            value = {"claudeAiOauth": {
                "accessToken": access,
                "refreshToken": refresh,
                "expiresAt": expires_seconds * 1000,
            }}
            command = "sync"
        elif kind == "kimi":
            path = home / ".kimi-code" / "credentials" / "kimi-code.json"
            value = {
                "access_token": access,
                "refresh_token": refresh,
                "expires_at": expires_seconds,
                "expires_in": 3600,
            }
            command = "sync"
        else:
            path = home / "codex-profiles" / profile / ".codex" / "auth.json"
            value = {
                "auth_mode": "chatgpt",
                "last_refresh": (
                    datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=generation)
                ).isoformat(),
                "tokens": {
                    "access_token": f"old-{access}",
                    "refresh_token": refresh,
                    "id_token": "fixture-id",
                },
            }
            self.oauth.token_body = {
                "access_token": access,
                "refresh_token": f"rotated-{refresh}",
                "id_token": "fixture-id",
            }
            command = "push"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        before = path.read_bytes()
        result = self.run(kind, command, profile, env)
        if result.returncode != 0:
            raise AssertionError(f"{self.transport} {kind}:{profile} owner failed: {result.stderr}")
        after = json.loads(path.read_text())
        if kind in ("claude", "kimi"):
            if path.read_bytes() != before:
                raise AssertionError(f"{kind}:{profile} owner credentials changed during sync")
        elif after["tokens"]["refresh_token"] != SENTINEL:
            raise AssertionError(f"codex:{profile} owner was not demoted after vault handoff")
        return access

    def follower_pull(self, kind, profile, follower):
        home, env = self.client_env(f"{follower}-{kind}", follower)
        result = self.run(kind, "pull", profile, env)
        if result.returncode != 0:
            raise AssertionError(f"{self.transport} {follower} pull {kind}:{profile} failed: {result.stderr}")
        if kind == "claude":
            value = json.loads((home / ".claude" / ".credentials.json").read_text())
            return value["accessToken"], value["refreshToken"]
        if kind == "kimi":
            value = json.loads((home / ".kimi-code" / "credentials" / "kimi-code.json").read_text())
            return value["access_token"], value["refresh_token"]
        value = json.loads((home / "codex-profiles" / profile / ".codex" / "auth.json").read_text())
        return value["tokens"]["access_token"], value["tokens"]["refresh_token"]


class FollowerLeaderMatrixTest(unittest.TestCase):
    def exercise(self, transport):
        token = {"access_token": "initial", "refresh_token": "initial"}
        with tempfile.TemporaryDirectory() as temporary, MockOAuthServer(200, token) as oauth:
            lab = FleetLab(temporary, transport, oauth)
            try:
                expected = {}
                for kind in ("claude", "kimi", "codex"):
                    for profile in lab.profiles:
                        with self.subTest(transport=transport, kind=kind, profile=profile, phase="owner"):
                            expected[kind, profile] = lab.owner_sync(kind, profile)

                for follower in lab.followers:
                    for kind in ("claude", "kimi", "codex"):
                        for profile in lab.profiles:
                            with self.subTest(transport=transport, follower=follower, kind=kind, profile=profile):
                                access, refresh = lab.follower_pull(kind, profile, follower)
                                self.assertEqual(access, expected[kind, profile])
                                self.assertEqual(refresh, SENTINEL)

                for kind in ("claude", "kimi", "codex"):
                    with self.subTest(transport=transport, kind=kind, phase="rotation"):
                        expected[kind, "alpha"] = lab.owner_sync(kind, "alpha", generation=2)
                        for follower in lab.followers:
                            access, refresh = lab.follower_pull(kind, "alpha", follower)
                            self.assertEqual(access, expected[kind, "alpha"])
                            self.assertEqual(refresh, SENTINEL)
                            beta_access, beta_refresh = lab.follower_pull(kind, "beta", follower)
                            self.assertEqual(beta_access, expected[kind, "beta"])
                            self.assertEqual(beta_refresh, SENTINEL)

                with self.subTest(transport=transport, kind="kimi", phase="expired-owner-authority"):
                    canonical = lab.leader / "kimi-profiles" / "alpha" / "credentials.json"
                    shared = lab.leader / "shared" / "kimi" / "alpha.json"
                    for path in (canonical, shared):
                        value = json.loads(path.read_text())
                        value["expires_at"] = 1
                        path.write_text(json.dumps(value))
                    follower_home, follower_env = lab.client_env("follower-a-kimi", "follower-a")
                    local = follower_home / ".kimi-code" / "credentials" / "kimi-code.json"
                    before = local.read_bytes()
                    canonical_before = canonical.read_bytes()
                    oauth_requests = len(oauth.requests)
                    expired = lab.run("kimi", "pull", "alpha", follower_env)
                    self.assertNotEqual(expired.returncode, 0)
                    self.assertEqual(local.read_bytes(), before)
                    self.assertEqual(canonical.read_bytes(), canonical_before)
                    self.assertEqual(len(oauth.requests), oauth_requests)

                outsider_home, outsider_env = lab.client_env("outsider", "outsider")
                for kind in ("claude", "kimi", "codex"):
                    with self.subTest(transport=transport, kind=kind, phase="acl-denial"):
                        denied = lab.run(kind, "pull", "alpha", outsider_env)
                        self.assertNotEqual(denied.returncode, 0)
                self.assertFalse((outsider_home / ".claude" / ".credentials.json").exists())
            finally:
                lab.close()

    def test_http_owner_leader_follower_matrix(self):
        self.exercise("http")

    def test_ssh_owner_leader_follower_matrix(self):
        self.exercise("ssh")

    def exercise_launch(self, transport):
        token = {"access_token": "initial", "refresh_token": "initial"}
        with tempfile.TemporaryDirectory() as temporary, MockOAuthServer(200, token) as oauth:
            lab = FleetLab(temporary, transport, oauth)
            try:
                expected = {
                    kind: lab.owner_sync(kind, "alpha")
                    for kind in ("claude", "kimi", "codex")
                }
                for kind in ("claude", "kimi", "codex"):
                    with self.subTest(transport=transport, kind=kind, phase="launch"):
                        home, env = lab.client_env(f"launch-{kind}", "follower-a")
                        env["CODEX_USER"] = "alpha"
                        capture = home / f"{kind}-launch.env"
                        executable = home / f"fake-{kind}"
                        executable.write_text(
                            "#!/usr/bin/env bash\n"
                            "printf '%s\\n' \"${ANTHROPIC_AUTH_TOKEN:-}\" "
                            "\"${KIMI_CODE_OAUTH_HOST:-}\" "
                            "\"${CODEX_REFRESH_TOKEN_URL_OVERRIDE:-}\" "
                            "\"$*\" > \"$CAPTURE_FILE\"\n"
                        )
                        executable.chmod(0o755)
                        env.update({
                            "CAPTURE_FILE": str(capture),
                            "CLAUDE_REAL_BIN": str(executable),
                            "KIMI_BIN": str(executable),
                            "CODEX_BIN": str(executable),
                            "TMPDIR": str(home),
                        })
                        result = subprocess.run(
                            [AI_TOKEN, kind, "run", "--probe"],
                            env=env,
                            text=True,
                            capture_output=True,
                            timeout=15,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        values = capture.read_text().splitlines()
                        self.assertEqual(values[3], "--probe")
                        if kind == "claude":
                            self.assertEqual(values[0], expected[kind])
                        elif kind == "kimi":
                            self.assertEqual(values[1], "http://127.0.0.1:9/oauth/token")
                        else:
                            self.assertEqual(values[2], "http://127.0.0.1:9/oauth/token")
            finally:
                lab.close()

    def test_http_follower_launch_matrix(self):
        self.exercise_launch("http")

    def test_ssh_follower_launch_matrix(self):
        self.exercise_launch("ssh")

    @staticmethod
    def owner_snapshot():
        return json.dumps({
            "claudeAiOauth": {
                "accessToken": "protocol-access",
                "refreshToken": "protocol-refresh",
                "expiresAt": (int(time.time()) + 3600) * 1000,
            }
        }).encode()

    def test_http_rejects_unversioned_and_legacy_writers(self):
        with tempfile.TemporaryDirectory() as temporary, MockOAuthServer() as oauth:
            lab = FleetLab(temporary, "http", oauth)
            try:
                def post(version=None):
                    headers = {
                        "Authorization": f"Bearer {lab.token('owner-alpha')}",
                        "Content-Type": "application/json",
                    }
                    if version is not None:
                        headers["X-Ai-Token-Version"] = version
                    request = urllib.request.Request(
                        f"{lab.base_url}/sync/claude/alpha",
                        data=self.owner_snapshot(),
                        headers=headers,
                        method="POST",
                    )
                    return urllib.request.urlopen(request, timeout=5)

                for version in (None, "2.9.9"):
                    with self.subTest(version=version):
                        with self.assertRaises(urllib.error.HTTPError) as rejected:
                            post(version)
                        self.assertEqual(rejected.exception.code, 426)
                with post("3.0.3") as accepted:
                    self.assertEqual(accepted.status, 200)
            finally:
                lab.close()

    def test_ssh_rejects_unversioned_and_legacy_writers(self):
        with tempfile.TemporaryDirectory() as temporary, MockOAuthServer() as oauth:
            lab = FleetLab(temporary, "ssh", oauth)
            try:
                _home, env = lab.client_env("protocol-owner", "owner-alpha", "owner")

                def post(command):
                    return subprocess.run(
                        [lab.bin / "ssh", "hermetic-leader", command],
                        input=self.owner_snapshot(),
                        env=env,
                        capture_output=True,
                        timeout=10,
                    )

                self.assertNotEqual(post("ai-vault sync-receive claude:alpha").returncode, 0)
                self.assertNotEqual(post("ai-vault client 2.9.9 sync-receive claude:alpha").returncode, 0)
                accepted = post("ai-vault client 3.0.3 sync-receive claude:alpha")
                self.assertEqual(accepted.returncode, 0, accepted.stderr.decode())
            finally:
                lab.close()


if __name__ == "__main__":
    unittest.main()
