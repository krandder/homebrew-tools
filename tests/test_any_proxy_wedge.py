#!/usr/bin/env python3
"""Regression tests for the 2026-07-22 claude any-proxy hung-listener wedge.

Incident: the any-proxy on the mac wedged after ~4h — LISTEN socket open but
unserving. Root cause: forward() called fetch() with NO timeout, so a stalled
upstream connection parked the request forever; retried clients
(CLAUDE_CODE_MAX_RETRIES=99) stacked sockets until the accept backlog filled.
launchd only restarts DEAD processes, not hung ones.

Spawns the REAL proxy (`node any-proxy.mjs <registry> <sharedDir>`) against a
fake upstream the test flips between "blackhole" (accepts, never responds)
and "healthy" (200 JSON {id, model, usage{...}}), with a tmp HOME holding
.claude-token/ and a shared dir with one fake profile. No network beyond
loopback; CLAUDE_PROXY_NO_HEAL=1 keeps ai-token out of the loop.

a. blackholed upstream -> 502/504 within CLAUDE_PROXY_UPSTREAM_TIMEOUT_MS+5s,
   and the NEXT request (upstream healthy again) still returns 200 — the
   proxy must NOT be stalled by the first blackholed request
b. stalled client request body -> /healthz still answers 200 within 2s
c. /healthz -> 200 {ok: true, inflight: n} while idle AND mid-blackhole
d. CLAUDE_PROXY_UPSTREAM_TIMEOUT_MS=1000 -> the 502 lands in <6s
"""

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
NODE = shutil.which("node")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(port, path="/v1/messages", body=b'{"x":1}', timeout=10):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body,
        headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class _UpstreamHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        while n > 0:
            chunk = self.rfile.read(min(n, 65536))
            if not chunk:
                break
            n -= len(chunk)
        if self.server.mode == "blackhole":
            # accept and never answer; the daemon thread is reaped at teardown
            time.sleep(60)
            return
        body = json.dumps({
            "id": "msg_fake1", "model": "claude-fake",
            "usage": {"input_tokens": 3, "output_tokens": 2},
        }).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class WedgeFixture(unittest.TestCase):
    UPSTREAM_TIMEOUT_MS = "3000"

    @classmethod
    def setUpClass(cls):
        if NODE is None:
            raise RuntimeError("node is required to run any-proxy.mjs")
        cls.upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
        cls.upstream.daemon_threads = True
        cls.upstream.mode = "healthy"
        cls.up_thread = threading.Thread(target=cls.upstream.serve_forever, daemon=True)
        cls.up_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.upstream.shutdown()
        cls.upstream.server_close()
        cls.up_thread.join(timeout=2)

    def setUp(self):
        type(self).upstream.mode = "healthy"
        self.tmp = Path(tempfile.mkdtemp(prefix="anywedge-"))
        home = self.tmp
        (home / ".claude-token").mkdir(parents=True)
        shared = home / "shared" / "claude-tokens"
        shared.mkdir(parents=True)
        now_ms = int(time.time() * 1000)
        (shared / "solo.json").write_text(json.dumps(
            {"claudeAiOauth": {"accessToken": "tok-fake", "expiresAt": now_ms + 3_600_000}}))
        registry = home / ".claude-token" / "proxy-ports.json"
        registry.write_text("{}")
        self.port = free_port()
        env = dict(os.environ)
        env.update({
            "HOME": str(home),
            "CLAUDE_PROXY_UPSTREAM": f"http://127.0.0.1:{self.upstream.server_address[1]}",
            "CLAUDE_PROXY_ANY_PORT": str(self.port),
            "CLAUDE_PROXY_NO_HEAL": "1",
            "CLAUDE_PROXY_UPSTREAM_TIMEOUT_MS": self.UPSTREAM_TIMEOUT_MS,
        })
        self.proc = subprocess.Popen(
            [NODE, str(ROOT / "any-proxy.mjs"), str(registry), str(shared)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 15
        while True:
            if self.proc.poll() is not None:
                raise AssertionError("any-proxy.mjs exited early")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                    break
            except OSError:
                if time.time() > deadline:
                    self.proc.kill()
                    raise AssertionError("any-proxy.mjs did not start listening")
                time.sleep(0.1)

    def tearDown(self):
        self.proc.kill()
        self.proc.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, timeout=10):
        return post(self.port, timeout=timeout)

    def healthz(self, timeout=2):
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/healthz", timeout=timeout) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, {}

    def blackhole(self):
        type(self).upstream.mode = "blackhole"

    def heal_upstream(self):
        type(self).upstream.mode = "healthy"


class TestBlackholeUpstream(WedgeFixture):
    def test_blackhole_times_out_and_proxy_keeps_serving(self):
        self.blackhole()
        budget = int(self.UPSTREAM_TIMEOUT_MS) / 1000 + 5
        t0 = time.monotonic()
        status, _ = self.post(timeout=budget + 2)
        elapsed = time.monotonic() - t0
        self.assertIn(status, (502, 504),
                      "blackholed upstream must surface as an upstream error")
        self.assertLess(elapsed, budget,
                        "the 502 must land within the upstream-timeout budget")
        # CRITICAL: the wedge — one blackholed request must not stall the proxy
        self.heal_upstream()
        status, body = self.post(timeout=10)
        self.assertEqual(status, 200,
                         "proxy wedged: request after the blackholed one was not served")
        self.assertEqual(json.loads(body)["id"], "msg_fake1")


class TestHealthz(WedgeFixture):
    def test_healthz_idle(self):
        status, body = self.healthz()
        self.assertEqual(status, 200)
        self.assertIs(body.get("ok"), True)
        self.assertEqual(body.get("inflight"), 0)
        self.assertIn("uptime_s", body)

    def test_healthz_reports_inflight_during_blackhole(self):
        self.blackhole()
        outcome = {}

        def call():
            outcome["result"] = post(self.port, timeout=15)

        t = threading.Thread(target=call, daemon=True)
        t.start()
        deadline = time.monotonic() + 2.5
        seen = None
        while time.monotonic() < deadline:
            status, body = self.healthz()
            if status == 200 and body.get("inflight", 0) >= 1:
                seen = body
                break
            time.sleep(0.05)
        t.join(timeout=15)
        self.assertIsNotNone(seen, "/healthz never reported the in-flight blackholed request")
        self.assertIs(seen.get("ok"), True)
        self.assertIn(outcome.get("result", (None,))[0], (502, 504))
        self.heal_upstream()

    def test_stalled_client_body_does_not_block_healthz(self):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        try:
            s.sendall(b"POST /v1/messages HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                      b"content-type: application/json\r\ncontent-length: 64\r\n\r\n"
                      b'{"model":"claude-fake","partial')
            time.sleep(3)
        finally:
            s.close()
        t0 = time.monotonic()
        status, body = self.healthz(timeout=2)
        self.assertEqual(status, 200)
        self.assertIs(body.get("ok"), True)
        self.assertLess(time.monotonic() - t0, 2)


class TestUpstreamTimeoutBudget(WedgeFixture):
    UPSTREAM_TIMEOUT_MS = "1000"

    def test_timeout_budget_env_is_honored(self):
        self.blackhole()
        t0 = time.monotonic()
        status, _ = self.post(timeout=8)
        elapsed = time.monotonic() - t0
        self.assertIn(status, (502, 504))
        self.assertLess(elapsed, 6, "a 1000ms budget must land the 502 well under 6s")


if __name__ == "__main__":
    unittest.main()
