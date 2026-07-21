#!/usr/bin/env python3
"""End-to-end tests for the standalone any-proxies (any-proxy.mjs,
codex-any-proxy.mjs, kimi-any-proxy.mjs).

Spawns the REAL proxy (bun or node, whatever is available) against a stub
upstream HTTP server and a tmp HOME; no network beyond loopback, no real
credential stores. CLAUDE_PROXY_UPSTREAM / CLAUDE_PROXY_ANY_PORT /
CLAUDE_PROXY_NO_HEAL=1 point the proxy at the fixture.

claude suite:
  a. fresh shared file -> request served by that profile (stub sees its bearer)
  b. expired shared file -> excluded; the fresh profile serves
  c. shared file written AFTER proxy start -> included without restart
     (the vault-enrollment de-hardcode regression: presence is enough)
  d. upstream 401 -> same request fails over, cooldown_401_until persisted,
     next request skips the cooled profile
  e. empty pool -> 503 + `pool-empty` in any.log
  f. usage tap -> any-usage.jsonl records the true profile, request_id, model
     and token fields for both non-stream JSON and SSE Anthropic responses

codex/kimi suites (lighter): one serve test from the local leader layout and
one shared-file-fallback test (profile exists only in the shared dir) each.
"""

import base64
import http.server
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_runtime():
    override = os.environ.get("ANY_POOL_RUNTIME")
    if override:
        return override
    bun = os.path.expanduser("~/.bun/bin/bun")
    if os.path.exists(bun):
        return bun
    for name in ("node", "bun"):
        path = shutil.which(name)
        if path:
            return path
    return None


RUNTIME = find_runtime()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(port, path, payload):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def wait_jsonl(path, count, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            lines = [l for l in Path(path).read_text().splitlines() if l.strip()]
            if len(lines) >= count:
                return [json.loads(l) for l in lines]
        time.sleep(0.1)
    raise AssertionError(f"{path} did not reach {count} jsonl record(s)")


def jwt_with_payload(payload):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}.sig"


def fake_jwt(exp):
    return jwt_with_payload({"exp": exp})


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n)
        token = (self.headers.get("authorization") or "").replace("Bearer ", "")
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}
        self.server.requests.append({
            "token": token, "path": self.path,
            "account_id": self.headers.get("chatgpt-account-id"),
        })
        status, headers, body = self.server.responder(token, payload, self.server)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class StubUpstream:
    def __init__(self, responder):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.responder = responder
        self.server.requests = []
        self.server.modes = {}  # token -> "429" (test-flippable upstream behavior)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def tokens_seen(self):
        return [r["token"] for r in self.server.requests]

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class ProxyCase(unittest.TestCase):
    SCRIPT = None      # proxy .mjs in the repo root
    RESPONDER = None   # staticmethod(token, payload) -> (status, headers, body)

    @classmethod
    def setUpClass(cls):
        if RUNTIME is None:
            raise RuntimeError("need bun or node to run the any-proxy")
        cls.upstream = StubUpstream(cls.RESPONDER)

    @classmethod
    def tearDownClass(cls):
        cls.upstream.stop()

    def prepare(self):
        """Hook: create fixture dirs/files before the proxy spawns."""

    def argv(self):
        return []

    def extra_env(self):
        return {}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="anypool-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.port = free_port()
        self.prepare()
        env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "CLAUDE_PROXY_UPSTREAM": self.upstream.url,
            "CLAUDE_PROXY_ANY_PORT": str(self.port),
            "CLAUDE_PROXY_NO_HEAL": "1",
        }
        env.update(self.extra_env())
        self.proc = subprocess.Popen(
            [RUNTIME, str(ROOT / self.SCRIPT), *self.argv()],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 15
        while True:
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"{self.SCRIPT} exited early: {self.proc.stderr.read().decode(errors='replace')}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                    break
            except OSError:
                if time.time() > deadline:
                    self.proc.kill()
                    raise AssertionError(f"{self.SCRIPT} did not start listening")
                time.sleep(0.1)

    def tearDown(self):
        self.proc.kill()
        self.proc.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, path="/v1/messages", payload=None):
        return post(self.port, path, payload if payload is not None else {"x": 1})


CLAUDE_USAGE_JSON = json.dumps({
    "id": "msg_json1", "type": "message", "model": "claude-test",
    "usage": {"input_tokens": 10, "output_tokens": 5,
              "cache_read_input_tokens": 3, "cache_creation_input_tokens": 7,
              "cache_creation": {"ephemeral_5m_input_tokens": 2,
                                 "ephemeral_1h_input_tokens": 1}},
}).encode()

CLAUDE_SSE = (
    'data: {"type":"message_start","message":{"id":"msg_sse1","type":"message",'
    '"model":"claude-test","usage":{"input_tokens":20,"output_tokens":1,'
    '"cache_read_input_tokens":4,"cache_creation_input_tokens":0}}}\n\n'
    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
    '"usage":{"output_tokens":9}}\n\n'
    'data: {"type":"message_stop"}\n\n'
).encode()


def claude_responder(token, payload, server=None):
    if token == "AT-A":
        return 401, {"content-type": "application/json"}, b'{"error":{"type":"authentication_error"}}'
    mode = (server.modes if server else {}).get(token)
    if mode == "429":
        return 429, {"content-type": "application/json"}, b'{"error":{"type":"rate_limit_error"}}'
    if mode and mode.isdigit():
        return int(mode), {"content-type": "application/json"}, b'{"error":{"type":"upstream_error","message":"stub 5xx/4xx"}}'
    if payload.get("stream"):
        return 200, {"content-type": "text/event-stream"}, CLAUDE_SSE
    if payload.get("usage"):
        return 200, {"content-type": "application/json"}, CLAUDE_USAGE_JSON
    return 200, {"content-type": "application/json"}, json.dumps(
        {"ok": True, "served_by": token}).encode()


def claude_profile(expires_in_hours, token):
    now_ms = int(time.time() * 1000)
    return {"claudeAiOauth": {"accessToken": token,
                              "expiresAt": now_ms + int(expires_in_hours * 3600e3)}}


class ClaudeAnyPoolTest(ProxyCase):
    SCRIPT = "any-proxy.mjs"
    RESPONDER = staticmethod(claude_responder)

    def prepare(self):
        self.shared = self.tmp / "shared" / "claude-tokens"
        self.shared.mkdir(parents=True)
        self.statedir = self.home / ".claude-token"
        self.statedir.mkdir()
        self.registry = self.statedir / "proxy-ports.json"
        self.registry.write_text("{}")

    def argv(self):
        return [str(self.registry), str(self.shared)]

    def write_shared(self, name, payload):
        (self.shared / f"{name}.json").write_text(json.dumps(payload))

    def state(self):
        f = self.statedir / "any-state.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def anylog(self):
        f = self.statedir / "any.log"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []

    def test_fresh_shared_file_serves(self):
        self.write_shared("solo", claude_profile(4, "AT-SOLO"))
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-SOLO")
        self.assertIn("AT-SOLO", self.upstream.tokens_seen())

    def test_expired_shared_file_is_excluded(self):
        self.write_shared("stale", claude_profile(-1, "AT-OLD"))
        self.write_shared("fresh1", claude_profile(4, "AT-F1"))
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-F1")
        self.assertNotIn("AT-OLD", self.upstream.tokens_seen())

    def test_new_shared_file_after_start_is_included(self):
        self.write_shared("old", claude_profile(4, "AT-OLD2"))
        status, body = self.post()
        self.assertEqual(json.loads(body)["served_by"], "AT-OLD2")
        # vault enrollment lands as a plain file; no proxy restart, no config
        self.write_shared("newp", claude_profile(4, "AT-NEW"))
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-NEW")

    def test_401_failover_then_cooldown_skips_profile(self):
        self.write_shared("alpha", claude_profile(4, "AT-A"))
        self.write_shared("beta", claude_profile(4, "AT-B"))
        (self.statedir / "any-state.json").write_text(
            json.dumps({"alpha": {"last_used": 1}, "beta": {"last_used": 2}}))
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-B",
                         "alpha 401s upstream -> same request must fail over to beta")
        self.assertGreater(self.state()["alpha"]["cooldown_401_until"], time.time())
        events = [(e["event"], e.get("profile")) for e in self.anylog()]
        self.assertIn(("failover", "alpha"), events)
        hits_before = self.upstream.tokens_seen().count("AT-A")
        status, body = self.post()
        self.assertEqual(json.loads(body)["served_by"], "AT-B")
        self.assertEqual(self.upstream.tokens_seen().count("AT-A"), hits_before,
                         "alpha is in cooldown: the next request must not retry it")

    def test_empty_pool_is_503_and_logs_pool_empty(self):
        self.write_shared("alpha", claude_profile(4, "AT-A2"))
        self.write_shared("beta", claude_profile(4, "AT-B2"))
        future = time.time() + 600
        (self.statedir / "any-state.json").write_text(json.dumps({
            "alpha": {"cooldown_401_until": future},
            "beta": {"cooldown_401_until": future},
        }))
        status, body = self.post()
        self.assertEqual(status, 503)
        self.assertIn(b"no healthy profile available", body)
        self.assertIn("pool-empty", [e["event"] for e in self.anylog()])
        self.assertGreater(self.state().get("pool_alert_last", 0), 0)

    def test_usage_tap_records_json_and_sse(self):
        self.write_shared("meter", claude_profile(4, "AT-M"))
        status, body = self.post(payload={"usage": 1})
        self.assertEqual(status, 200)
        status, body = self.post(payload={"stream": True})
        self.assertEqual(status, 200)
        records = wait_jsonl(self.statedir / "any-usage.jsonl", 2)
        by_id = {r["request_id"]: r for r in records}
        self.assertEqual(set(by_id), {"msg_json1", "msg_sse1"})
        plain = by_id["msg_json1"]
        self.assertEqual(plain["source"], "claude-proxy")
        self.assertEqual(plain["profile"], "meter")
        self.assertEqual(plain["model"], "claude-test")
        self.assertEqual(plain["input_tokens"], 10)
        self.assertEqual(plain["output_tokens"], 5)
        self.assertEqual(plain["cache_read"], 3)
        self.assertEqual(plain["cache_write_5m"], 6,
                         "unattributed cache_creation remainder rolls into the 5m bucket")
        self.assertEqual(plain["cache_write_1h"], 1)
        sse = by_id["msg_sse1"]
        self.assertEqual(sse["profile"], "meter")
        self.assertEqual(sse["model"], "claude-test")
        self.assertEqual(sse["input_tokens"], 20)
        self.assertEqual(sse["output_tokens"], 9,
                         "SSE output_tokens come from message_delta, not message_start")
        self.assertEqual(sse["cache_read"], 4)

    def test_429_failover_is_transparent_and_cools_profile(self):
        self.write_shared("quota", claude_profile(4, "AT-Q"))
        self.write_shared("beta", claude_profile(4, "AT-B"))
        self.upstream.server.modes["AT-Q"] = "429"
        (self.statedir / "any-state.json").write_text(
            json.dumps({"quota": {"last_used": 1}, "beta": {"last_used": 2}}))
        status, body = self.post()
        self.assertEqual(status, 200, "the client must never see the upstream 429")
        self.assertEqual(json.loads(body)["served_by"], "AT-B",
                         "quota 429s -> the SAME request must fail over to beta")
        self.assertGreater(self.state()["quota"]["cooldown_429_until"], time.time())
        events = [(e["event"], e.get("profile"), e.get("kind")) for e in self.anylog()]
        self.assertIn(("failover", "quota", "429"), events)

    def test_429_cooldown_skips_then_serves_after_expiry(self):
        self.write_shared("recovering", claude_profile(4, "AT-R"))
        self.write_shared("steady", claude_profile(4, "AT-OK"))
        self.upstream.server.modes["AT-R"] = "429"
        (self.statedir / "any-state.json").write_text(
            json.dumps({"recovering": {"last_used": 1}, "steady": {"last_used": 2}}))
        status, body = self.post()
        self.assertEqual(json.loads(body)["served_by"], "AT-OK")
        self.assertGreater(self.state()["recovering"]["cooldown_429_until"], time.time())
        status, body = self.post()
        self.assertEqual(json.loads(body)["served_by"], "AT-OK")
        self.assertEqual(self.upstream.tokens_seen().count("AT-R"), 1,
                         "recovering is 429-cooled: the next request must not retry it")
        # cooldown passes and upstream recovers: the profile serves again
        st = self.state()
        st["recovering"]["cooldown_429_until"] = time.time() - 1
        (self.statedir / "any-state.json").write_text(json.dumps(st))
        self.upstream.server.modes["AT-R"] = "ok"
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-R",
                         "an expired 429 cooldown must make the profile pickable again")

    def test_all_429_yields_503_and_pool_empty(self):
        self.write_shared("qa", claude_profile(4, "AT-QA"))
        self.write_shared("qb", claude_profile(4, "AT-QB"))
        self.upstream.server.modes["AT-QA"] = "429"
        self.upstream.server.modes["AT-QB"] = "429"
        status, body = self.post()
        self.assertEqual(status, 503)
        self.assertIn(b"no healthy profile available", body)
        self.assertNotIn(b"rate_limit_error", body,
                         "the raw upstream 429 body must never leak to the client")
        self.assertIn("pool-empty", [e["event"] for e in self.anylog()])

    def test_429_cooldown_is_the_1800s_class(self):
        self.write_shared("quota", claude_profile(4, "AT-Q"))
        self.write_shared("beta", claude_profile(4, "AT-B"))
        self.upstream.server.modes["AT-Q"] = "429"
        (self.statedir / "any-state.json").write_text(
            json.dumps({"quota": {"last_used": 1}, "beta": {"last_used": 2}}))
        status, body = self.post()
        self.assertEqual(status, 200)
        delta = self.state()["quota"]["cooldown_429_until"] - time.time()
        self.assertGreater(delta, 1200,
                           "429 cooldown must be the 1800s class, not the 401's 900s")
        self.assertLessEqual(delta, 1800 + 5)

    def test_5xx_failover_is_transparent_and_cools_profile(self):
        self.write_shared("flaky", claude_profile(4, "AT-X"))
        self.write_shared("beta", claude_profile(4, "AT-B"))
        self.upstream.server.modes["AT-X"] = "529"
        (self.statedir / "any-state.json").write_text(
            json.dumps({"flaky": {"last_used": 1}, "beta": {"last_used": 2}}))
        status, body = self.post()
        self.assertEqual(status, 200, "the client must never see the upstream 529")
        self.assertEqual(json.loads(body)["served_by"], "AT-B",
                         "flaky 529s -> the SAME request must fail over to beta")
        delta = self.state()["flaky"]["cooldown_5xx_until"] - time.time()
        self.assertGreater(delta, 120)
        self.assertLessEqual(delta, 300 + 5)
        self.assertLess(delta, 900,
                        "5xx cooldown is the 300s class, clearly below 401/429 classes")
        events = [(e["event"], e.get("profile"), e.get("kind"), e.get("status"))
                  for e in self.anylog()]
        self.assertIn(("failover", "flaky", "5xx", 529), events)

    def test_5xx_cooldown_skips_then_serves_after_expiry(self):
        self.write_shared("recovering", claude_profile(4, "AT-R2"))
        self.write_shared("steady", claude_profile(4, "AT-OK"))
        self.upstream.server.modes["AT-R2"] = "529"
        (self.statedir / "any-state.json").write_text(
            json.dumps({"recovering": {"last_used": 1}, "steady": {"last_used": 2}}))
        status, body = self.post()
        self.assertEqual(json.loads(body)["served_by"], "AT-OK")
        self.assertGreater(self.state()["recovering"]["cooldown_5xx_until"], time.time())
        status, body = self.post()
        self.assertEqual(json.loads(body)["served_by"], "AT-OK")
        self.assertEqual(self.upstream.tokens_seen().count("AT-R2"), 1,
                         "recovering is 5xx-cooled: the next request must not retry it")
        st = self.state()
        st["recovering"]["cooldown_5xx_until"] = time.time() - 1
        (self.statedir / "any-state.json").write_text(json.dumps(st))
        self.upstream.server.modes["AT-R2"] = "ok"
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-R2",
                         "an expired 5xx cooldown must make the profile pickable again")

    def test_all_5xx_yields_503_and_pool_empty(self):
        self.write_shared("xa", claude_profile(4, "AT-XA"))
        self.write_shared("xb", claude_profile(4, "AT-XB"))
        self.upstream.server.modes["AT-XA"] = "529"
        self.upstream.server.modes["AT-XB"] = "529"
        status, body = self.post()
        self.assertEqual(status, 503)
        self.assertIn(b"no healthy profile available", body)
        self.assertNotIn(b"upstream_error", body,
                         "the raw upstream 5xx body must never leak to the client")
        self.assertIn("pool-empty", [e["event"] for e in self.anylog()])

    def test_400_forwards_untouched_without_cooldown(self):
        self.write_shared("solo", claude_profile(4, "AT-BAD"))
        self.upstream.server.modes["AT-BAD"] = "400"
        hits_before = len(self.upstream.tokens_seen())
        status, body = self.post()
        self.assertEqual(status, 400, "a client error must be forwarded as-is")
        self.assertIn(b"upstream_error", body)
        self.assertEqual(len(self.upstream.tokens_seen()), hits_before + 1,
                         "no failover retry may happen on a 4xx client error")
        ent = self.state().get("solo", {})
        for key in ("cooldown_401_until", "cooldown_429_until", "cooldown_5xx_until"):
            self.assertNotIn(key, ent, "client errors must never cool a profile")
        self.assertNotIn("failover", [e["event"] for e in self.anylog()])


CODEX_RESPONSE = json.dumps({
    "id": "resp_c", "object": "response", "model": "gpt-test",
    "usage": {"input_tokens": 12, "output_tokens": 4,
              "input_tokens_details": {"cached_tokens": 5}},
}).encode()


def codex_responder(token, payload, server=None):
    mode = (server.modes if server else {}).get(token)
    if mode and mode.isdigit():
        return int(mode), {"content-type": "application/json"}, b'{"error":{"type":"upstream_error","message":"stub 5xx/4xx"}}'
    body = json.loads(CODEX_RESPONSE)
    body["served_by"] = token
    return 200, {"content-type": "application/json"}, json.dumps(body).encode()


class CodexAnyPoolTest(ProxyCase):
    SCRIPT = "codex-any-proxy.mjs"
    RESPONDER = staticmethod(codex_responder)

    def prepare(self):
        self.profiles = self.tmp / "codex-profiles"
        self.shared = self.tmp / "codex-shared"
        self.profiles.mkdir()
        self.shared.mkdir()

    def extra_env(self):
        return {"CODEX_PROFILES_DIR": str(self.profiles),
                "CODEX_SHARED_DIR": str(self.shared)}

    def write_local(self, profile, token, account_id=None, id_token=None):
        d = self.profiles / profile / ".codex"
        d.mkdir(parents=True)
        tokens = {"access_token": token, "refresh_token": "sentinel-follower"}
        if account_id:
            tokens["account_id"] = account_id
        if id_token:
            tokens["id_token"] = id_token
        (d / "auth.json").write_text(json.dumps({"tokens": tokens}))

    def test_local_profile_serves(self):
        at = fake_jwt(int(time.time()) + 3600)
        self.write_local("p1", at, account_id="acc-9")
        status, body = self.post(path="/responses")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], at)
        seen = self.upstream.server.requests[-1]
        self.assertEqual(seen["account_id"], "acc-9",
                         "the proxy must forward the profile's chatgpt-account-id")
        records = wait_jsonl(self.profiles / "any-usage.jsonl", 1)
        self.assertEqual(records[0]["source"], "codex-proxy")
        self.assertEqual(records[0]["profile"], "p1")
        self.assertEqual(records[0]["input_tokens"], 7,
                         "cached_tokens are subtracted from billable input")
        self.assertEqual(records[0]["cache_read"], 5)

    def test_shared_only_profile_serves(self):
        at = fake_jwt(int(time.time()) + 3600)
        (self.shared / "p2.json").write_text(json.dumps(
            {"tokens": {"access_token": at, "refresh_token": "x"}}))
        status, body = self.post(path="/responses")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], at,
                         "a profile that exists only in the shared dir must still serve")

    def test_free_plan_profile_never_serves(self):
        future = int(time.time()) + 3600
        # identical freshness, distinct token strings
        at_free = jwt_with_payload({"exp": future, "sub": "free-plan-user"})
        at_plus = jwt_with_payload({"exp": future, "sub": "plus-plan-user"})
        id_free = jwt_with_payload(
            {"https://api.openai.com/auth": {"chatgpt_plan_type": "free"}})
        id_plus = jwt_with_payload(
            {"https://api.openai.com/auth": {"chatgpt_plan_type": "plus"}})
        self.write_local("free", at_free, id_token=id_free)
        self.write_local("plus", at_plus, id_token=id_plus)
        (self.profiles / "any-state.json").write_text(
            json.dumps({"free": {"last_used": 1}, "plus": {"last_used": 2}}))
        status, body = self.post(path="/responses")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], at_plus,
                         "a free-plan profile must be excluded even with a fresh access_token")
        self.assertNotIn(at_free, self.upstream.tokens_seen())

    def test_5xx_failover_cools_profile(self):
        future = int(time.time()) + 3600
        at_a = jwt_with_payload({"exp": future, "sub": "user-a"})
        at_b = jwt_with_payload({"exp": future, "sub": "user-b"})
        self.write_local("p5a", at_a)  # no id_token: plan undecodable fails open
        self.write_local("p5b", at_b)
        (self.profiles / "any-state.json").write_text(
            json.dumps({"p5a": {"last_used": 1}, "p5b": {"last_used": 2}}))
        self.upstream.server.modes[at_a] = "503"
        status, body = self.post(path="/responses")
        self.assertEqual(status, 200, "the client must never see the upstream 503")
        self.assertEqual(json.loads(body)["served_by"], at_b,
                         "p5a 503s -> the SAME request must fail over to p5b")
        state = json.loads((self.profiles / "any-state.json").read_text())
        delta = state["p5a"]["cooldown_5xx_until"] - time.time()
        self.assertGreater(delta, 120)
        self.assertLessEqual(delta, 300 + 5)
        log_lines = (self.profiles / "any.log").read_text().splitlines()
        events = [(json.loads(l)["event"], json.loads(l).get("profile"),
                   json.loads(l).get("kind"), json.loads(l).get("status"))
                  for l in log_lines]
        self.assertIn(("failover", "p5a", "5xx", 503), events)


KIMI_RESPONSE = json.dumps({
    "id": "chatcmpl_k", "object": "chat.completion", "model": "kimi-test",
    "usage": {"prompt_tokens": 8, "completion_tokens": 3,
              "prompt_tokens_details": {"cached_tokens": 2}},
}).encode()


def kimi_responder(token, payload, server=None):
    body = json.loads(KIMI_RESPONSE)
    body["served_by"] = token
    return 200, {"content-type": "application/json"}, json.dumps(body).encode()


class KimiAnyPoolTest(ProxyCase):
    SCRIPT = "kimi-any-proxy.mjs"
    RESPONDER = staticmethod(kimi_responder)

    def prepare(self):
        self.profiles = self.tmp / "kimi-profiles"
        self.shared = self.tmp / "kimi-shared"
        self.profiles.mkdir()
        self.shared.mkdir()
        (self.home / ".kimi-code").mkdir()

    def extra_env(self):
        return {"KIMI_PROFILES_DIR": str(self.profiles),
                "KIMI_SHARED_DIR": str(self.shared)}

    def test_local_profile_serves(self):
        d = self.profiles / "k1"
        d.mkdir(parents=True)
        (d / "credentials.json").write_text(json.dumps(
            {"access_token": "AT-K1", "expires_at": time.time() + 3600}))
        status, body = self.post(path="/chat/completions")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-K1")
        records = wait_jsonl(self.home / ".kimi-code" / "any-usage.jsonl", 1)
        self.assertEqual(records[0]["source"], "kimi-proxy")
        self.assertEqual(records[0]["profile"], "k1")
        self.assertEqual(records[0]["input_tokens"], 6)
        self.assertEqual(records[0]["cache_read"], 2)

    def test_shared_only_profile_serves(self):
        (self.shared / "k2.json").write_text(json.dumps(
            {"access_token": "AT-K2", "expires_at": time.time() + 3600}))
        status, body = self.post(path="/chat/completions")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-K2",
                         "a profile that exists only in the shared dir must still serve")


if __name__ == "__main__":
    unittest.main()
