import hmac
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .companion_assets import SPRITES, POSES
from .coopanion import asset_path, ACTIONS, SCHEMES, OUTFITS


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
            static = {"/": (Path(__file__).parent / "web/index.html", "text/html; charset=utf-8"),
                      "/style.css": (Path(__file__).parent / "web/style.css", "text/css; charset=utf-8"),
                      "/app.js": (Path(__file__).parent / "web/app.js", "text/javascript; charset=utf-8")}
            static["/renderer"] = (Path(__file__).parent / "web/renderer.html", "text/html; charset=utf-8")
            static["/renderer.js"] = (Path(__file__).parent / "web/renderer.js", "text/javascript; charset=utf-8")
            static['/pet_motion.js']=(Path(__file__).parent/'web/pet_motion.js','text/javascript; charset=utf-8')
            from urllib.parse import urlsplit
            path_only = urlsplit(self.path).path
            if path_only.startswith("/coopanion/"):
                path = asset_path(path_only[len("/coopanion/"):])
                if path:
                    types = {".js":"text/javascript; charset=utf-8", ".json":"application/json; charset=utf-8", ".css":"text/css; charset=utf-8", ".png":"image/png", ".webp":"image/webp", ".svg":"image/svg+xml"}
                    static[path_only] = (path, types[path.suffix])
            for pose in POSES:
                static[f"/companion/{pose}.png"] = (SPRITES / f"dafeiyu-{pose}.png", "image/png")
            if path_only in static:
                path, content_type = static[path_only]
                if not path.is_file():
                    return self.send_json(404, {"error": "asset_not_installed"})
                body = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Security-Policy", "frame-ancestors 'self'" if path_only=="/renderer" else "frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
                return
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            if self.path == "/v1/status":
                return self.send_json(200, engine.status())
            if self.path == "/v1/companion/catalog":
                return self.send_json(200, {"actions": ACTIONS, "schemes": SCHEMES, "outfits": OUTFITS})
            if self.path == "/v1/observations/latest":
                return self.send_json(200, {"observation": engine.latest()})
            if self.path == "/v1/chat/status":
                return self.send_json(200, {"jobs":dict(engine.chat_receipts)})
            if self.path == '/v1/desktop':
                try:return self.send_json(200,engine.desktop_info())
                except ValueError:return self.send_json(409,{'error':'watching_paused'})
            if self.path == '/v1/sessions/pending':
                return self.send_json(200,{'sessions':engine.sessions.pending()})
            if self.path == '/v1/sessions':
                return self.send_json(200,{'sessions':engine.sessions.recent()})
            if self.path == '/v1/sessions/missing-summaries':
                return self.send_json(200,{'ids':engine.sessions.missing_summaries()})
            if self.path == '/v1/voice/bank':
                from .voice_bank import catalog
                return self.send_json(200,{'phrases':catalog(engine.root)})
            if self.path == '/v1/extension/download':
                import io,zipfile
                source=Path(__file__).resolve().parents[1]/'browser-extension'
                buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
                    for name in ('manifest.json','background.js','popup.html','popup.js','INSTALL.md'):
                        if (source/name).is_file():z.write(source/name,'xiaojing-browser-extension/'+name)
                body=buffer.getvalue()
                self.send_response(200);self.send_header('Content-Type','application/zip')
                self.send_header('Content-Disposition','attachment; filename="xiaojing-browser-extension.zip"')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                return
            if self.path.startswith('/v1/pet/commands/'):
                try:
                    with engine.lock:record=engine.pet_feedback.get(self.path.rsplit('/',1)[-1])
                    return self.send_json(200,record)
                except ValueError:return self.send_json(404,{'error':'unknown_command'})
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
                elif self.path == '/v1/chat':
                    return self.send_json(200,{'id':engine.submit_chat(data.get('text'),data.get('initiative',False),data.get('generation'))})
                elif self.path == '/v1/chat/take':
                    return self.send_json(200,{'job':engine.take_chat()})
                elif self.path == '/v1/chat/reply':
                    engine.desktop_reply(data['text'],data['session'],data['job_id'])
                elif self.path == '/v1/sessions/ack':
                    engine.sessions.acknowledge(data['id'],data['memory_id'],data.get('summary'))
                elif self.path == '/v1/voice/cached':
                    engine.cached_voice(data['id'],data['generation'])
                elif self.path == '/v1/voice/bank/preview':
                    from .voice_bank import audio_path
                    audio_path(engine.root,data['id'])
                    if not engine.pet_state.get('ready'):raise ValueError('桌面播放器尚未就绪')
                    with engine.lock:engine.voice_commands.append({'cached':data['id'],'preview':True,'generation':engine.generation})
                elif self.path == '/v1/voice/stop':
                    with engine.lock:
                        engine.voice_commands.clear();engine.voice_commands.append({'stop':True})
                elif self.path == "/v1/watching":
                    if type(data.get("enabled")) is not bool:
                        raise ValueError("enabled 须为布尔值")
                    engine.set_enabled(data["enabled"])
                elif self.path == "/v1/text":
                    engine.ingest_text(data)
                elif self.path == "/v1/replies":
                    engine.publish_reply(data["text"], data["observation_id"], data["session"], data["generation"])
                elif self.path == "/v1/pet/action":
                    return self.send_json(200,{'id':engine.pet_action(data['pose']),'state':'queued'})
                elif self.path == '/v1/pet/move':
                    return self.send_json(200,{'id':engine.pet_move(data['target'],data.get('x'),data.get('y'),data.get('app',''),data.get('side','right')),'state':'queued'})
                elif self.path == "/v1/bridge/heartbeat":
                    import time
                    engine.bridge = {"connected_at": time.time(), "vision_configured": bool(data.get("vision_configured")),
                                     'vision_min_seconds':int(data.get('vision_min_seconds',60)),
                                     'initiative_seconds':int(data.get('initiative_seconds',900)),
                                     'initiative_enabled':bool(data.get('initiative_enabled',False)),
                                     "phase": data.get("phase", "idle") if data.get("phase", "idle") in ("idle","analyzing","chat") else "idle"}
                elif self.path == '/v1/voice/enabled':
                    engine.voice_control.toggle(data['enabled'])
                elif self.path == "/v1/voice/test":
                    import requests
                    session = requests.Session()
                    session.trust_env = False
                    try:
                        r = session.get(engine.config["voice_url"].rstrip("/") + "/v1/capabilities",
                                        headers={"Authorization": "Bearer " + engine.config["voice_key"]},
                                        timeout=8, allow_redirects=False)
                        r.raise_for_status()
                        capability = r.json()
                        available = any(row.get("available") for row in capability.get("tts", []))
                        engine.voice_status.update(diagnostic_available=available)
                    except Exception:
                        engine.voice_status.update(diagnostic_available=False)
                    finally:
                        session.close()
                elif self.path == "/v1/voice/preview":
                    if not engine.pet_state.get("ready") or engine.voice_status.get('state') != 'ready':
                        raise ValueError("桌宠或声音服务尚未就绪")
                    with engine.lock:
                        engine.voice_commands.append("你好呀，我是小鲸。今天也一起待在这里吧。")
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
