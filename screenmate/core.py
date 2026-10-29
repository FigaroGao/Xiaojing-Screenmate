from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from PIL import ImageGrab

DEFAULTS = dict(interval=15.0, mode="mixed", skip_unchanged=True,
                monitor_bbox=None, text_ttl=45, observation_ttl=90,
                voice_url="http://127.0.0.1:9880", voice_key="", voice_style="cute",
                pet_size=218, activity="balanced", reduced_motion=False, bubbles=True)


class Engine:
    def __init__(self, root: Path, capture=None):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "settings.private.json"
        self.config = dict(DEFAULTS)
        if self.path.exists():
            self.config.update(json.loads(self.path.read_text(encoding="utf-8")))
        self.config.setdefault("token", secrets.token_urlsafe(32))
        self.save()
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.enabled = False
        self.generation = 0
        self.observation = None
        self.text = None
        self.reply = None
        self.error = ""
        self.last_hash = None
        self.sequence = 0
        self.session = secrets.token_hex(12)
        self.observed = {}
        self.capture = capture or self._capture
        self.capture_guard = threading.Lock()
        self.pet_commands = deque(maxlen=16)
        self.pet_state = {"pose": "idle", "label": "待机", "ready": False}
        self.bridge = {"connected_at": None}
        self.voice_status = {"checked": False, "available": False}

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def configure(self, values):
        interval = float(values.get("interval", self.config["interval"]))
        if not 1 <= interval <= 3600:
            raise ValueError("观察间隔须在 1 至 3600 秒之间")
        mode = values.get("mode", self.config["mode"])
        if mode not in ("text", "vision", "mixed"):
            raise ValueError("未知观察模式")
        pet_size = int(values.get("pet_size", self.config["pet_size"]))
        if not 100 <= pet_size <= 400:
            raise ValueError("桌宠大小须在 100 至 400 之间")
        activity = values.get("activity", self.config["activity"])
        if activity not in ("quiet", "balanced", "lively"):
            raise ValueError("未知活跃程度")
        for key in ("skip_unchanged", "reduced_motion", "bubbles"):
            if key in values and type(values[key]) is not bool:
                raise ValueError("需要布尔值")
        if values.get("voice_style", self.config["voice_style"]) not in ("cute", "gentle"):
            raise ValueError("未知声线")
        voice_url = values.get("voice_url", self.config["voice_url"])
        url = urlsplit(voice_url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("声音服务需要有效的 HTTP 或 HTTPS 地址")
        bbox = values.get("monitor_bbox", self.config["monitor_bbox"])
        if bbox is not None:
            if not isinstance(bbox, list) or len(bbox) != 4 or any(type(n) is not int for n in bbox):
                raise ValueError("区域格式为 [左, 上, 右, 下]")
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                raise ValueError("区域宽高必须大于零")
        with self.lock:
            observation_changed = any(key in values for key in ("interval", "mode", "monitor_bbox", "skip_unchanged"))
            if observation_changed:
                self.generation += 1
                self.observation = None
                self.observed.clear()
                self.last_hash = None
            self.config.update(interval=interval, mode=mode, monitor_bbox=bbox,
                               skip_unchanged=bool(values.get("skip_unchanged", self.config["skip_unchanged"])))
            for key in ("voice_url", "voice_key", "voice_style"):
                if key in values:
                    self.config[key] = str(values[key])
            self.config.update(pet_size=pet_size, activity=activity)
            for key in ("reduced_motion", "bubbles"):
                if key in values:
                    self.config[key] = values[key]
            self.save()
        if observation_changed:
            self.wake.set()

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = bool(enabled)
            self.generation += 1
            self.observation = None
            self.observed.clear()
            self.last_hash = None
            self.text = None
            self.error = ""
        self.wake.set()

    def ingest_text(self, data):
        with self.lock:
            if not self.enabled:
                raise ValueError("观看已暂停")
            self.text = dict(title=str(data.get("title", ""))[:500],
                             url=str(data.get("url", ""))[:2000],
                             text=str(data.get("text", ""))[:24000],
                             received_at=time.time(), source="browser-visible-text")

    @staticmethod
    def _capture(bbox):
        # Windows secure desktop / lock screen: do not serve an old frame.
        import ctypes
        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = ctypes.c_void_p
        desktop = user32.OpenInputDesktop(0, False, 0x0100)
        if not desktop:
            raise RuntimeError("无法访问当前桌面，可能已锁屏")
        try:
            if not user32.SwitchDesktop(ctypes.c_void_p(desktop)):
                raise RuntimeError("桌面已锁定或不可见")
        finally:
            user32.CloseDesktop(ctypes.c_void_p(desktop))
        return ImageGrab.grab(bbox=tuple(bbox) if bbox else None, all_screens=True)

    def sample(self):
        if not self.capture_guard.acquire(blocking=False):
            return
        try:
            with self.lock:
                if not self.enabled:
                    return
                generation, config = self.generation, dict(self.config)
                text = dict(self.text) if self.text else None
            if text and time.time() - text["received_at"] > config["text_ttl"]:
                text = None
            image = None
            fingerprint = json.dumps(text and {k: v for k, v in text.items() if k != "received_at"}, sort_keys=True)
            if config["mode"] != "text":
                shot = self.capture(config["monitor_bbox"])
                shot.thumbnail((1600, 1000))
                out = io.BytesIO()
                shot.convert("RGB").save(out, format="JPEG", quality=80)
                image = base64.b64encode(out.getvalue()).decode()
                fingerprint += hashlib.sha256(out.getvalue()).hexdigest()
            elif text is None:
                raise RuntimeError("等待浏览器发送可见文字；请连接扩展并开启当前页")
            digest = hashlib.sha256(fingerprint.encode()).hexdigest()
            with self.lock:
                if not self.enabled or generation != self.generation:
                    return
                self.error = ""
                if config["skip_unchanged"] and digest == self.last_hash:
                    if self.observation:
                        self.observation["captured_at"] = time.time()
                        self.observed[self.sequence] = (generation, time.time())
                    return
                self.sequence += 1
                self.observation = dict(id=self.sequence, captured_at=time.time(), mode=config["mode"],
                                        session=self.session, generation=generation,
                                        text=text if config["mode"] != "vision" else None,
                                        image_base64=image, mime="image/jpeg" if image else None,
                                        source="screenmate", region=config["monitor_bbox"])
                self.last_hash = digest
                self.observed[self.sequence] = (generation, time.time())
                while len(self.observed) > 32:
                    self.observed.pop(next(iter(self.observed)))
        except Exception as exc:
            with self.lock:
                if generation == self.generation:
                    self.error = str(exc)
                    self.observation = None
                    self.observed.clear()
        finally:
            self.capture_guard.release()

    def latest(self):
        with self.lock:
            obs = self.observation
            if not self.enabled or not obs or time.time() - obs["captured_at"] > self.config["observation_ttl"]:
                return None
            return dict(obs)

    def publish_reply(self, text, observation_id, session=None, generation=None):
        with self.lock:
            if session is not None and (session != self.session or generation != self.generation):
                raise ValueError("观看会话已经变化")
            observed = self.observed.get(observation_id)
            if not self.enabled or not observed or observed[0] != self.generation or time.time() - observed[1] > self.config["observation_ttl"]:
                raise ValueError("画面已过期或观看已暂停，丢弃旧回复")
            self.reply = dict(text=str(text)[:6000], observation_id=observation_id, at=time.time())

    def status(self):
        with self.lock:
            return dict(enabled=self.enabled, interval=self.config["interval"], mode=self.config["mode"],
                        skip_unchanged=self.config["skip_unchanged"], monitor_bbox=self.config["monitor_bbox"],
                        error=self.error, sequence=self.sequence, reply=self.reply,
                        companion=dict(self.pet_state), bridge=dict(self.bridge), voice=dict(self.voice_status),
                        preferences={k: self.config[k] for k in ("pet_size", "activity", "reduced_motion", "bubbles", "voice_url", "voice_style")},
                        voice_configured=bool(self.config["voice_key"]),
                        observation_time=self.observation["captured_at"] if self.latest() else None,
                        has_observation=self.latest() is not None)

    def pet_action(self, pose):
        from .companion_assets import POSES
        if pose not in POSES:
            raise ValueError("未知动作")
        with self.lock:
            self.pet_commands.append(pose)

    def run(self):
        while not self.stop_event.is_set():
            self.wake.clear()
            self.sample()
            self.wake.wait(self.config["interval"])

    def close(self):
        self.set_enabled(False)
        self.stop_event.set()
        self.wake.set()
