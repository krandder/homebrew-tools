#!/usr/bin/env python3
"""Hermetic tests for the claude-token proxy ANY-port (proxy.mjs).

Spawns the REAL proxy (bun) against a fake upstream server and a fake HOME:
- failover: profile A gets a 401 upstream -> same request succeeds on B,
  A is cooled down, and the NEXT request skips A entirely.
- 429 failover likewise (different cooldown key).
- spread-load: two healthy profiles alternate across consecutive requests.
- non-auth upstream errors are passed through, not retried.
- exhausted pool -> 503, honest error.

No network beyond localhost; NO_HEAL=1 keeps ai-token out of the loop.
"""

import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path

REPO_PROXY = os.path.expanduser("~/.claude-token/proxy.mjs")
ANY_PORT = 17811
UP_PORT = 17812


class FakeUpstream(http.server.BaseHTTPRequestHandler):
    # token -> (status, body). "A" 401s, "B" 200s, "C" never used, "Q" 429s.
    def do_POST(self):
        token = (self.headers.get("authorization") or "").replace("Bearer ", "")
        n = int(self.headers.get("content-length") or 0)
        self.rfile.read(n)
        if token == "AT-A":
            status, body = 401, b'{"error":{"type":"authentication_error"}}'
        elif token == "AT-Q":
            status, body = 429, b'{"error":{"type":"rate_limit_error"}}'
        elif token == "AT-ERR":
            status, body = 400, b'{"error":{"type":"invalid_request_error","message":"bad input"}}'
        elif token.startswith("AT-"):
            status, body = 200, json.dumps({"served_by": token}).encode()
        else:
            status, body = 500, b"?"
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def post(port, path="/v1/messages", body=b'{"x":1}'):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body,
        headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class ProxyFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = http.server.HTTPServer(("127.0.0.1", UP_PORT), FakeUpstream)
        cls.up_thread = threading.Thread(target=cls.upstream.serve_forever, daemon=True)
        cls.up_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.upstream.shutdown()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="anyproxy-"))
        home = self.tmp
        (home / ".claude-token").mkdir(parents=True)
        (home / "shared/claude-tokens").mkdir(parents=True)
        now_ms = int(time.time() * 1000)
        for name, token, hours in (("alpha", "AT-A", 4), ("beta", "AT-B", 4),
                                   ("gone", "AT-G", -1), ("quota", "AT-Q", 4),
                                   ("badreq", "AT-ERR", 4),
                                   ("one", "AT-1", 4), ("two", "AT-2", 4)):
            (home / "shared/claude-tokens" / f"{name}.json").write_text(json.dumps({
                "claudeAiOauth": {"accessToken": token, "expiresAt": now_ms + int(hours * 3600e3)}}))
        (home / ".claude-token/proxy-ports.json").write_text(
            json.dumps({"alpha": 17901, "beta": 17904, "gone": 17905, "quota": 17902,
                        "badreq": 17903, "one": 17906, "two": 17907}))
        env = dict(os.environ)
        env.update({
            "HOME": str(home),
            "CLAUDE_PROXY_UPSTREAM": f"http://127.0.0.1:{UP_PORT}",
            "CLAUDE_PROXY_ANY_PORT": str(ANY_PORT),
            "CLAUDE_PROXY_NO_HEAL": "1",
        })
        self.proc = subprocess.Popen(
            ["bun", REPO_PROXY, str(home / ".claude-token/proxy-ports.json"),
             str(home / "shared/claude-tokens")],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", ANY_PORT), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.25)

    def tearDown(self):
        self.proc.kill()
        self.proc.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self):
        f = self.tmp / ".claude-token/any-state.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def anylog(self):
        f = self.tmp / ".claude-token/any.log"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


class TestAnyPort(ProxyFixture):
    def test_401_failover_and_cooldown(self):
        future = time.time() + 600
        st0 = {"quota": {"cooldown_429_until": future}, "badreq": {"cooldown_401_until": future},
               "one": {"cooldown_401_until": future}, "two": {"cooldown_401_until": future}}
        (self.tmp / ".claude-token/any-state.json").write_text(json.dumps(st0))
        status, body = post(ANY_PORT)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-B",
                         "alpha 401s upstream -> request must be served by beta")
        st = self.state()
        self.assertGreater(st["alpha"]["cooldown_401_until"], time.time())
        events = [(e["event"], e.get("profile")) for e in self.anylog()]
        self.assertIn(("failover", "alpha"), events)
        # next request: alpha in cooldown -> beta picked directly, no new failover
        status, body = post(ANY_PORT)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["served_by"], "AT-B")
        self.assertEqual([(e["event"]) for e in self.anylog()].count("failover"), 1)

    def test_429_failover_marks_429_cooldown(self):
        st0 = {"quota": {"last_used": 1}, "beta": {"last_used": 2}, "alpha": {"last_used": 3},
               "badreq": {"last_used": 4}, "one": {"last_used": 5}, "two": {"last_used": 6}}
        (self.tmp / ".claude-token/any-state.json").write_text(json.dumps(st0))
        status, body = post(ANY_PORT)
        self.assertEqual(status, 200, "quota 429s -> failover to beta must still serve")
        self.assertEqual(json.loads(body)["served_by"], "AT-B")
        st = self.state()
        self.assertGreater(st["quota"]["cooldown_429_until"], time.time())

    def test_spread_load_rotates(self):
        future = time.time() + 600
        st0 = {"quota": {"cooldown_429_until": future}, "badreq": {"cooldown_401_until": future},
               "alpha": {"cooldown_401_until": future}}
        (self.tmp / ".claude-token/any-state.json").write_text(json.dumps(st0))
        served = set()
        for _ in range(3):
            status, body = post(ANY_PORT)
            self.assertEqual(status, 200)
            served.add(json.loads(body)["served_by"])
        self.assertEqual(served, {"AT-1", "AT-2", "AT-B"},
                         "spread-load must rotate across all three healthy profiles")

    def test_nonauth_error_passes_through(self):
        st0 = {"badreq": {"last_used": 1}, "alpha": {"last_used": 2}, "beta": {"last_used": 3},
               "quota": {"last_used": 4}, "one": {"last_used": 5}, "two": {"last_used": 6}}
        (self.tmp / ".claude-token/any-state.json").write_text(json.dumps(st0))
        status, body = post(ANY_PORT)
        self.assertEqual(status, 400, "non-auth upstream errors must pass through, no failover")
        self.assertNotIn("cooldown_429_until", self.state().get("badreq", {}))

    def test_exhausted_pool_503(self):
        (self.tmp / ".claude-token/any-state.json").write_text(json.dumps({
            "alpha": {"cooldown_401_until": time.time() + 600},
            "beta": {"cooldown_401_until": time.time() + 600},
            "quota": {"cooldown_429_until": time.time() + 600},
            "badreq": {"cooldown_401_until": time.time() + 600},
            "one": {"cooldown_401_until": time.time() + 600},
            "two": {"cooldown_401_until": time.time() + 600},
        }))
        status, body = post(ANY_PORT)
        self.assertEqual(status, 503)
        self.assertIn(b"no healthy profile", body)


if __name__ == "__main__":
    unittest.main()
