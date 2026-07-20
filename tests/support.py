import http.server
import json
import threading
import time


class MockOAuthServer:
    def __init__(self, token_status=200, token_body=None, profile_status=200, profile_body=None, delay=0,
                 token_headers=None, profile_headers=None):
        self.token_status = token_status
        self.token_body = token_body or {}
        self.profile_status = profile_status
        self.profile_body = profile_body or {}
        self.delay = delay
        self.token_headers = token_headers or {}
        self.profile_headers = profile_headers or {}
        self.requests = []
        scenario = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                scenario.requests.append(("POST", self.path, dict(self.headers), body))
                if scenario.delay:
                    time.sleep(scenario.delay)
                self.respond(scenario.token_status, scenario.token_body, scenario.token_headers)

            def do_GET(self):
                scenario.requests.append(("GET", self.path, dict(self.headers), b""))
                self.respond(scenario.profile_status, scenario.profile_body, scenario.profile_headers)

            def respond(self, status, body, headers):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def token_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/oauth/token"

    @property
    def profile_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/profile"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
