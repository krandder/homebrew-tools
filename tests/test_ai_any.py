#!/usr/bin/env python3
"""Hermetic tests for ai-any (claude-any / codex-any).

Fake HOME per test: proxy-ports, shared token files with real expiry math,
canonicals with needsRelogin markers, codex JWTs (hand-minted, unsigned),
and fake CLI wrappers whose per-launch behavior is scriptable
(ok / 401 / 429 / boom). Asserts selection policy, exclusion rules, retry
chains, cooldown persistence, main-account last-resort, and failure honesty.
"""

import base64
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_loader = SourceFileLoader("ai_any", str(ROOT / "ai-any"))
_spec = importlib.util.spec_from_loader("ai_any", _loader)
ai_any = importlib.util.module_from_spec(_spec)
_loader.exec_module(ai_any)

H = 3600_000  # one hour in ms


def jwt(exp_s):
    def b64(d):
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()
    return f"{b64(b'{}')}.{b64(json.dumps({'exp': exp_s}).encode())}.sig"


def make_claude_profile(home, name, *, expires_in_h=4.0, needs_relogin=False):
    (home / "shared/claude-tokens").mkdir(parents=True, exist_ok=True)
    (home / "shared/claude-tokens" / f"{name}.json").write_text(json.dumps({
        "claudeAiOauth": {"accessToken": f"AT-{name}", "expiresAt": int(time.time() * 1000 + expires_in_h * H)}
    }))
    cred_dir = home / ".claude-profiles" / name / ".claude"
    cred_dir.mkdir(parents=True, exist_ok=True)
    (cred_dir / "credentials.json").write_text(json.dumps({
        "claudeAiOauth": {"accessToken": f"AT-{name}"},
        "claudeTokenSync": {"refreshAuthority": "vault", **({"needsRelogin": True} if needs_relogin else {})},
    }))


def make_codex_profile(home, name, *, expires_in_s=4 * 3600):
    d = home / ".codex-profiles" / name / ".codex"
    d.mkdir(parents=True, exist_ok=True)
    (d / "auth.json").write_text(json.dumps({"tokens": {"access_token": jwt(time.time() + expires_in_s)}}))


def make_fake_cli(home, plans, test_env=None):
    """bin/<name> scripts: each run pops the first line of its .plan file and
    prints it ('ok'->rc0, '401'/'429'->rc1 with matching text, 'boom'->rc3)."""
    bin_dir = home / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "fake-cli"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "self=$(basename \"$0\")\n"
        "plan=\"$FAKE_HOME/bin/$self.plan\"\n"
        "[ -f \"$plan\" ] || { echo ok; exit 0; }\n"
        "line=$(head -1 \"$plan\"); tail -n +2 \"$plan\" > \"$plan.tmp\"; mv \"$plan.tmp\" \"$plan\"\n"
        "case \"$line\" in\n"
        "  ok) echo ok; exit 0;;\n"
        "  401) echo 'API Error: 401 Invalid authentication credentials'; exit 1;;\n"
        "  429) echo 'API Error: 429 rate_limit_error: usage limit reached'; exit 1;;\n"
        "  boom) echo 'segfault'; exit 3;;\n"
        "esac\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    for name, lines in plans.items():
        link = bin_dir / name
        if not link.exists():
            link.symlink_to(script)
        (bin_dir / f"{name}.plan").write_text("\n".join(lines) + "\n")
    if test_env is not None:
        test_env["PATH"] = str(bin_dir) + ":" + test_env.get("PATH", "")
    return bin_dir


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", ""), "FAKE_HOME": str(self.home)}
        self.argv0 = sys.argv[0]

    def tearDown(self):
        self.tmp.cleanup()

    def fake_cli(self, plans):
        return make_fake_cli(self.home, plans, self.env)

    def run_any(self, kind, args, argv0=None):
        argv0 = argv0 or f"{kind}-any"
        with mock.patch.dict(os.environ, dict(self.env), clear=False), \
                mock.patch.object(sys, "argv", [argv0] + args), \
                mock.patch.object(ai_any.os, "execvp", side_effect=RuntimeError("execvp")) as ex:
            try:
                rc = ai_any.main()
            except RuntimeError as e:
                if "execvp" not in str(e):
                    raise
                rc = ("interactive", ex.call_args[0][0], ex.call_args[0][1])
        return rc

    def state(self):
        f = self.home / (".claude-token" if self.kind == "claude" else ".codex-profiles") / "any-state.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def log_lines(self):
        f = self.home / (".claude-token" if self.kind == "claude" else ".codex-profiles") / "any.log"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


class TestClaudeAny(Base):
    kind = "claude"

    def setup_profiles(self):
        (self.home / ".claude-token").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude-token/proxy-ports.json").write_text(
            json.dumps({"kas": 7801, "mnx": 7804, "adriana": 7805}))

    def test_spread_load_picks_least_recently_used(self):
        self.setup_profiles()
        for p in ("kas", "mnx", "adriana"):
            make_claude_profile(self.home, p)
        self.fake_cli({"claude-kas": ["ok"], "claude-mnx": ["ok"], "claude-adriana": ["ok"]})
        seen = set()
        for _ in range(3):
            rc = self.run_any("claude", ["-p", "hi"])
            self.assertEqual(rc, 0)
            seen.add(self.log_lines()[-1]["profile"])
        self.assertEqual(seen, {"kas", "mnx", "adriana"}, "spread-load must rotate across all working profiles")

    def test_needs_relogin_and_expired_excluded(self):
        self.setup_profiles()
        make_claude_profile(self.home, "kas")
        make_claude_profile(self.home, "mnx", needs_relogin=True)
        make_claude_profile(self.home, "adriana", expires_in_h=-1)
        self.fake_cli({"claude-kas": ["ok"]})
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        picks = [e["profile"] for e in self.log_lines() if e["event"] == "select"]
        self.assertEqual(picks, ["kas"])

    def test_401_retry_marks_cooldown_and_moves_on(self):
        self.setup_profiles()
        make_claude_profile(self.home, "kas")
        make_claude_profile(self.home, "mnx")
        self.fake_cli({"claude-kas": ["401", "ok"], "claude-mnx": ["ok"]})
        # force kas to be least-recently-used so it goes first
        st = {"kas": {"last_used": 1}, "mnx": {"last_used": 2}}
        (self.home / ".claude-token/any-state.json").write_text(json.dumps(st))
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        events = [(e["event"], e.get("profile")) for e in self.log_lines()]
        self.assertIn(("cooldown", "kas"), events)
        self.assertIn(("ok", "mnx"), events)
        self.assertGreater(self.state()["kas"]["cooldown_401_until"], time.time())
        # next run: kas is in cooldown, mnx is picked immediately
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        self.assertEqual([e["profile"] for e in self.log_lines() if e["event"] == "select"][-1], "mnx")

    def test_nonauth_failure_not_retried(self):
        self.setup_profiles()
        make_claude_profile(self.home, "kas")
        make_claude_profile(self.home, "mnx")
        self.fake_cli({"claude-kas": ["boom"], "claude-mnx": ["ok"]})
        st = {"kas": {"last_used": 1}, "mnx": {"last_used": 2}}
        (self.home / ".claude-token/any-state.json").write_text(json.dumps(st))
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 3, "non-auth failures must surface, not be masked by retries")
        self.assertEqual([e for e in self.log_lines() if e["event"] == "retry"], [])

    def test_main_is_last_resort_only(self):
        self.setup_profiles()
        make_claude_profile(self.home, "kas", expires_in_h=-1)  # dead
        self.fake_cli({"claude": ["ok"]})
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        self.assertIn(("select", "main"), [(e["event"], e.get("profile")) for e in self.log_lines()])

    def test_interactive_launches_without_retry(self):
        self.setup_profiles()
        make_claude_profile(self.home, "kas")
        rc = self.run_any("claude", [])
        self.assertEqual(rc[0], "interactive")
        self.assertEqual(rc[1], "claude-kas")


class TestCodexAny(Base):
    kind = "codex"

    def test_codex_candidates_and_retry(self):
        make_codex_profile(self.home, "adriana")
        make_codex_profile(self.home, "kas", expires_in_s=-100)  # dead JWT
        make_codex_profile(self.home, "mnx")
        self.fake_cli({"codex-adriana": ["429", "ok"], "codex-mnx": ["ok"]})
        st = {"adriana": {"last_used": 1}, "mnx": {"last_used": 2}}
        (self.home / ".codex-profiles/any-state.json").write_text(json.dumps(st))
        rc = self.run_any("codex", ["exec", "hi"])
        self.assertEqual(rc, 0)
        events = [(e["event"], e.get("profile")) for e in self.log_lines()]
        self.assertNotIn(("select", "kas"), events, "dead-JWT profile must not be selected")
        self.assertIn(("cooldown", "adriana"), events)
        self.assertIn(("ok", "mnx"), events)

    def test_codex_exhausted_errors(self):
        make_codex_profile(self.home, "kas", expires_in_s=-100)
        rc = self.run_any("codex", ["exec", "hi"])
        self.assertEqual(rc, 1)


def make_fake_ai_token(home, rc=0):
    """Fake ai-token in PATH: records every call, exits with rc."""
    bin_dir = home / "bin"
    bin_dir.mkdir(exist_ok=True)
    f = bin_dir / "ai-token"
    f.write_text(
        "#!/usr/bin/env bash\n"
        "echo \"$@\" >> \"$FAKE_HOME/bin/ai-token.calls\"\n"
        f"exit {rc}\n")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def ai_token_calls(home):
    f = home / "bin/ai-token.calls"
    return f.read_text().splitlines() if f.exists() else []


class TestHeal(Base):
    kind = "claude"

    def _claude_two_profiles(self):
        (self.home / ".claude-token").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude-token/proxy-ports.json").write_text(json.dumps({"kas": 7801, "mnx": 7804}))
        make_claude_profile(self.home, "kas")
        make_claude_profile(self.home, "mnx")
        self.fake_cli({"claude-kas": ["401"], "claude-mnx": ["ok"]})
        st = {"kas": {"last_used": 1}, "mnx": {"last_used": 2}}
        (self.home / ".claude-token/any-state.json").write_text(json.dumps(st))
        self.env["PATH"] = str(self.home / "bin") + ":" + self.env["PATH"]

    def test_401_triggers_leader_publish_and_clears_cooldown(self):
        self._claude_two_profiles()
        make_fake_ai_token(self.home, rc=0)
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        self.assertEqual(ai_token_calls(self.home), ["claude publish --profile kas"])
        st = self.state()
        self.assertNotIn("cooldown_401_until", st.get("kas", {}), "healed profile must be eligible again")

    def test_leader_heal_never_forces_refresh_authority_takeover(self):
        self._claude_two_profiles()
        fake = make_fake_ai_token(self.home, rc=0)
        ai_token = fake / "ai-token"
        ai_token.write_text(
            "#!/usr/bin/env bash\n"
            "echo \"${CLAUDE_TOKEN_VAULT_AUTHORITY:-unset}\" > \"$FAKE_HOME/bin/authority.env\"\n"
            "echo \"$@\" >> \"$FAKE_HOME/bin/ai-token.calls\"\n"
            "exit 0\n"
        )
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        self.assertEqual((self.home / "bin/authority.env").read_text().strip(), "unset")

    def test_401_on_follower_pulls_instead(self):
        self._claude_two_profiles()
        (self.home / ".claude-token/config").write_text("mode=follower\n")
        make_fake_ai_token(self.home, rc=0)
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)
        self.assertEqual(ai_token_calls(self.home), ["claude pull --profile kas"])

    def test_failed_heal_keeps_cooldown(self):
        self._claude_two_profiles()
        make_fake_ai_token(self.home, rc=1)
        rc = self.run_any("claude", ["-p", "hi"])
        self.assertEqual(rc, 0)  # mnx still serves the call
        self.assertGreater(self.state()["kas"]["cooldown_401_until"], time.time())

    def test_codex_follower_role_file_pulls(self):
        d = self.home / ".codex-profiles" / "adriana" / ".codex"
        d.mkdir(parents=True)
        (d / "auth.json").write_text(json.dumps({"tokens": {"access_token": jwt(time.time() + 3600)}}))
        (self.home / ".codex-profiles/adriana/.role").write_text("follower")
        make_codex_profile(self.home, "kas")
        self.fake_cli({"codex-adriana": ["401"], "codex-kas": ["ok"]})
        make_fake_ai_token(self.home, rc=0)
        st_dir = self.home / ".codex-profiles"
        (st_dir / "any-state.json").write_text(json.dumps({"adriana": {"last_used": 1}, "kas": {"last_used": 2}}))
        self.env["PATH"] = str(self.home / "bin") + ":" + self.env["PATH"]
        rc = self.run_any("codex", ["exec", "hi"])
        self.assertEqual(rc, 0)
        self.assertEqual(ai_token_calls(self.home), ["codex pull --profile adriana"])


if __name__ == "__main__":
    unittest.main()
