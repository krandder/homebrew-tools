import gzip
import http.client
import http.server
import json
import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AI_TOKEN = ROOT / "ai-token"


class ProxyTest(unittest.TestCase):
    def test_generated_proxy_accepts_a_hermetic_upstream(self):
        with tempfile.TemporaryDirectory() as directory:
            home = pathlib.Path(directory)
            env = {
                **os.environ,
                "HOME": str(home),
                "AI_TOKEN_REAL_HOME": str(home),
                "CLAUDE_PROXY_RUNTIME": "/bin/true",
                "CLAUDE_PROXY_REGISTRY": str(home / "registry.json"),
                "CLAUDE_SHARED_DIR": str(home / "shared"),
                "AI_TOKEN_LOG_DIR": str(home / "logs"),
                "PATH": "/usr/bin:/bin",
            }
            result = subprocess.run(
                [AI_TOKEN, "claude", "proxy"], env=env, text=True,
                capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = (home / ".claude-token" / "proxy.mjs").read_text()
            self.assertIn('process.env.CLAUDE_PROXY_UPSTREAM', generated)

    def test_proxy_replaces_auth_and_does_not_forward_stale_gzip_metadata(self):
        runtime = shutil.which("node")
        self.assertIsNotNone(runtime, "Node is required for the hermetic proxy contract test")
        requests = []

        class Upstream(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                requests.append(({key.lower(): value for key, value in self.headers.items()}, body))
                compressed = gzip.compress(b"proxy-ok")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(compressed)))
                self.end_headers()
                self.wfile.write(compressed)

            def log_message(self, *_args):
                pass

        upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        with tempfile.TemporaryDirectory() as directory:
            home = pathlib.Path(directory)
            shared = home / "shared"
            shared.mkdir()
            (shared / "fixture.json").write_text(json.dumps({
                "claudeAiOauth": {"accessToken": "published-access"},
            }))
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                proxy_port = reservation.getsockname()[1]
            registry = home / "registry.json"
            registry.write_text(json.dumps({"fixture": proxy_port}))
            env = {
                **os.environ,
                "HOME": str(home),
                "AI_TOKEN_REAL_HOME": str(home),
                "CLAUDE_PROXY_RUNTIME": runtime,
                "CLAUDE_PROXY_REGISTRY": str(registry),
                "CLAUDE_SHARED_DIR": str(shared),
                "CLAUDE_PROXY_UPSTREAM": f"http://127.0.0.1:{upstream.server_port}",
                "AI_TOKEN_LOG_DIR": str(home / "logs"),
                "PATH": "/usr/bin:/bin",
            }
            proxy = subprocess.Popen(
                [AI_TOKEN, "claude", "proxy"], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                for _ in range(100):
                    with socket.socket() as probe:
                        if probe.connect_ex(("127.0.0.1", proxy_port)) == 0:
                            break
                    time.sleep(0.02)
                else:
                    self.fail("proxy did not listen")

                connection = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=5)
                connection.request(
                    "POST", "/v1/messages?beta=true", body=b"request-body",
                    headers={"Authorization": "Bearer stale", "X-Api-Key": "stale-key"},
                )
                response = connection.getresponse()
                body = response.read()
                response_headers = {key.lower(): value for key, value in response.getheaders()}
                connection.close()

                (shared / "fixture.json").write_text(json.dumps({
                    "claudeAiOauth": {"accessToken": "rotated-access"},
                }))
                rotated = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=5)
                rotated.request("POST", "/v1/messages", body=b"second-request")
                rotated_response = rotated.getresponse()
                self.assertEqual(rotated_response.read(), b"proxy-ok")
                rotated.close()
            finally:
                proxy.terminate()
                try:
                    proxy.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    proxy.kill()
                    proxy.communicate(timeout=3)

        upstream.shutdown()
        upstream.server_close()
        upstream_thread.join(timeout=2)
        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"proxy-ok")
        self.assertNotIn("content-encoding", response_headers)
        self.assertNotIn("content-length", response_headers)
        self.assertEqual(requests[0][0]["authorization"], "Bearer published-access")
        self.assertNotIn("x-api-key", requests[0][0])
        self.assertEqual(requests[0][1], b"request-body")
        self.assertEqual(requests[1][0]["authorization"], "Bearer rotated-access")
        self.assertEqual(requests[1][1], b"second-request")


if __name__ == "__main__":
    unittest.main()
