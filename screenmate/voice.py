"""Feiyu asynchronous jobs; latest utterance wins; audio stays in memory."""
import io
import re
import threading
import time
import wave
from array import array
import math

import requests


class FeiyuVoice:
    def __init__(self, config):
        self.config = config
        self.generation = 0
        self.error = ""
        self.speaking = False
        self.envelope = []
        self.started = 0
        self.generating = False

    def stop(self):
        self.generation += 1
        self.speaking = False
        self.envelope = []
        self.generating = False
        import winsound
        winsound.PlaySound(None, 0)

    @staticmethod
    def pcm_envelope(samples, width, channels, rate):
        if width == 2:
            values = array('h', samples)
            scale = 32768
        elif width == 1:
            values = [n-128 for n in samples]
            scale = 128
        else:
            return []
        stride = max(1, int(rate*channels*.05))
        levels = [min(1, math.sqrt(sum(v*v for v in values[i:i+stride])/max(1,len(values[i:i+stride])))/scale*5)
                  for i in range(0,len(values),stride)]
        return levels

    def mouth_level(self):
        if not self.speaking or not self.envelope:
            return 0.0
        index = int((time.monotonic()-self.started)/.05)
        return self.envelope[index] if 0<=index<len(self.envelope) else 0.0

    def say(self, text):
        self.stop()
        generation = self.generation
        self.generating = True
        threading.Thread(target=self._work, args=(text, generation), daemon=True).start()

    def _work(self, text, generation):
        config = dict(self.config)
        if not config.get("voice_key"):
            self.error = "本地声音服务尚未配置密钥"
            self.generating = False
            return
        self.error = ""
        session = requests.Session()
        session.trust_env = False
        session.headers["Authorization"] = "Bearer " + config["voice_key"]
        base = config["voice_url"].rstrip("/")

        def request(method, path, **kwargs):
            response = session.request(method, base + path, timeout=20, allow_redirects=False, **kwargs)
            if not 200 <= response.status_code < 300:
                raise RuntimeError(f"声音服务 HTTP {response.status_code}")
            return response
        try:
            job = request("POST", "/v1/speech", json=dict(voice="feiyu", text=text[:2000],
                                                        style=config["voice_style"])).json()["id"]
            if not re.fullmatch(r"[0-9a-f]{32}", job):
                raise ValueError("声音服务返回了无效任务编号")
            deadline = time.monotonic() + 900
            while generation == self.generation and time.monotonic() < deadline:
                status = request("GET", f"/v1/jobs/{job}").json()["status"]
                if status in ("failed", "interrupted"):
                    raise RuntimeError("语音任务未完成")
                if status == "success":
                    response = request("GET", f"/v1/jobs/{job}/audio", stream=True)
                    audio = bytearray()
                    for chunk in response.iter_content(65536):
                        audio.extend(chunk)
                        if len(audio) > 32 * 1024**2:
                            raise ValueError("语音文件过大")
                    with wave.open(io.BytesIO(audio)) as wav:
                        if wav.getcomptype() != "NONE":
                            raise ValueError("需要 PCM WAV 音频")
                        envelope = self.pcm_envelope(wav.readframes(wav.getnframes()),wav.getsampwidth(),wav.getnchannels(),wav.getframerate())
                    if generation == self.generation:
                        import winsound
                        self.speaking = True
                        self.generating = False
                        self.envelope = envelope
                        self.started = time.monotonic()
                        winsound.PlaySound(bytes(audio), winsound.SND_MEMORY)
                    return
                time.sleep(0.5)
            if generation == self.generation:
                raise TimeoutError("语音生成超时")
        except Exception as exc:
            if generation == self.generation:
                self.error = str(exc)
        finally:
            if generation == self.generation:
                self.speaking = False
                self.generating = False
            session.close()
