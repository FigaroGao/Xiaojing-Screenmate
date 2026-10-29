import hmac
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def create_server(engine, host="127.0.0.1", port=17860):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log content, request URLs, or authorization headers.

        def send_json(self, code, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            expected = "Bearer " + engine.config["token"]
            return hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected.encode())

        def do_GET(self):
            if self.path == "/":
                body = (Path(__file__).parent / "web" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
                return
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            if self.path == "/v1/status":
                return self.send_json(200, engine.status())
            if self.path == "/v1/observations/latest":
                return self.send_json(200, {"observation": engine.latest()})
            self.send_json(404, {"error": "not_found"})

        def do_POST(self):
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 100000:
                    return self.send_json(413, {"error": "body_too_large"})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("请求须为 JSON 对象")
                if self.path == "/v1/settings":
                    engine.configure(data)
                elif self.path == "/v1/watching":
                    if type(data.get("enabled")) is not bool:
                        raise ValueError("enabled 须为布尔值")
                    engine.set_enabled(data["enabled"])
                elif self.path == "/v1/text":
                    engine.ingest_text(data)
                elif self.path == "/v1/replies":
                    engine.publish_reply(data["text"], data["observation_id"], data["session"], data["generation"])
                else:
                    return self.send_json(404, {"error": "not_found"})
                self.send_json(200, {"ok": True})
            except (ValueError, KeyError, TypeError):
                self.send_json(400, {"error": "invalid_request"})
    class ExclusiveServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
    server = ExclusiveServer((host, port), Handler)
    server.daemon_threads = True
    return server
