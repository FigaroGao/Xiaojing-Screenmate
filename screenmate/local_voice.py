"""Start the installed, private Feiyu service without touching other listeners."""
import json
import os
from pathlib import Path
import subprocess
import threading

import requests


def start_installed_voice(engine):
    def start():
        root = Path(__file__).resolve().parents[1]
        server = root / "runtime/feiyu-voice/server"
        python = server / ".venv/Scripts/pythonw.exe"
        config = server / "configs/voice_service.json"
        key_path = server / ".runtime/voice-service/api_key.txt"
        if os.name != "nt" or not all(p.is_file() for p in (python, config, key_path)):
            return
        key = key_path.read_text(encoding="utf-8").strip()
        base = engine.config.get("voice_url", "").rstrip("/")
        if base not in ("http://127.0.0.1:9880", "http://127.0.0.1:9881") or engine.config.get("voice_key") != key:
            return
        session = requests.Session()
        session.trust_env = False
        try:
            session.get(base+"/v1/capabilities", timeout=1,
                        headers={"Authorization": "Bearer " + key})
            return  # Any existing listener belongs to its current owner.
        except requests.ConnectionError:
            pass
        except requests.RequestException:
            return
        finally:
            session.close()
        with (server / ".runtime/voice-service/launcher.log").open("ab") as log:
            if base.endswith(":9881"):
                profile = json.loads((root / "runtime/voice-linux/tts/runtime.local.json").read_text(encoding="utf-8"))
                options_path = root / 'runtime/resident-voice.private.json'
                options = json.loads(options_path.read_text(encoding='utf-8')) if options_path.is_file() else {}
                precision = options.get('precision','fp32')
                if precision not in ('fp32','fp16','int8'):
                    return
                linux_root = '/mnt/' + root.drive[0].lower() + root.as_posix()[2:]
                command = ["wsl.exe", "-d", profile["distribution"], "-e", "env",
                           "LD_LIBRARY_PATH="+profile["python_library_dir"],
                           "SCREENMATE_VOICE_PRECISION="+precision,profile["python"],"-B",
                           linux_root+"/tools/resident_voice.py"]
            else:
                command = [str(python), "-m", "feiyu_voice_service", "--config", str(config),
                           "--host", "127.0.0.1", "--port", "9880"]
            return subprocess.Popen(command, cwd=server,
                             stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    return start()


class VoiceControl:
    """Explicit, session-only opt-in. Loading never blocks capture or chat."""
    def __init__(self, engine):
        self.engine = engine
        self.desired = False
        self.process = None
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.closed = False
        self.set_status('off', '语音已关闭，陪看和文字聊天可正常使用')
        threading.Thread(target=self.run, daemon=True).start()

    def set_status(self, state, message):
        self.engine.voice_status = dict(checked=True, available=state == 'ready', state=state,
                                       enabled=self.desired, message=message)

    def toggle(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('需要布尔值')
        with self.lock:
            if enabled == self.desired and self.engine.voice_status.get('state') in ('loading','ready','off'):
                return
            self.desired = enabled
            if not enabled:
                self.engine.voice_commands.clear()
                self.engine.voice_commands.append({'stop': True})
            self.set_status('loading' if enabled else 'stopping',
                            '正在加载语音，首次约需3分钟；可以继续文字聊天' if enabled else '正在关闭语音并释放模型')
        self.wake.set()

    def run(self):
        while not self.closed:
            self.wake.wait(); self.wake.clear()
            with self.lock:
                wanted = self.desired
            try:
                if not wanted:
                    self.shutdown()
                    with self.lock:
                        if not self.desired: self.set_status('off', '语音已关闭，陪看和文字聊天可正常使用')
                    continue
                if self.process is None or self.process.poll() is not None:
                    self.process = start_installed_voice(self.engine)
                import time
                deadline = time.monotonic() + 600
                while self.desired and not self.closed:
                    try:
                        with requests.Session() as http:
                            http.trust_env = False
                            r = http.get(self.engine.config['voice_url'].rstrip('/')+'/v1/capabilities',
                                         headers={'Authorization':'Bearer '+self.engine.config['voice_key']},
                                         timeout=2, allow_redirects=False)
                            r.raise_for_status(); data = r.json()
                        if data.get('error'): raise RuntimeError('语音模型加载失败，请检查服务日志')
                        if any(v.get('available') for v in data.get('tts', [])):
                            with self.lock:
                                if self.desired: self.set_status('ready', '语音已就绪')
                            break
                    except requests.RequestException:
                        pass
                    if time.monotonic() > deadline: raise RuntimeError('语音加载超时，可关闭后重新开启')
                    self.wake.wait(1); self.wake.clear()
                if not self.desired: self.wake.set()
            except Exception as exc:
                with self.lock:
                    if not self.closed: self.set_status('failed', str(exc))

    def shutdown(self):
        # Only this authenticated local resident service supports shutdown.
        base = self.engine.config.get('voice_url', '').rstrip('/')
        if base == 'http://127.0.0.1:9881':
            try:
                with requests.Session() as http:
                    http.trust_env = False
                    r = http.post(base+'/v1/shutdown', headers={'Authorization':'Bearer '+self.engine.config['voice_key']}, timeout=3, allow_redirects=False)
                    if r.status_code != 200: raise RuntimeError('服务不支持卸载，请更新本地语音服务')
                    import time
                    for _ in range(40):
                        try:
                            http.get(base+'/v1/capabilities', headers={'Authorization':'Bearer '+self.engine.config['voice_key']}, timeout=1, allow_redirects=False)
                        except requests.ConnectionError:
                            break
                        time.sleep(.2)
                    else:
                        raise RuntimeError('语音服务尚未退出，请查看本地服务状态')
            except requests.ConnectionError:
                pass
        elif self.process is None and self.desired is False:
            # A separately configured service is not ours to terminate.
            return
        if self.process is not None:
            try: self.process.wait(timeout=8)
            except subprocess.TimeoutExpired: self.process.terminate()
            self.process = None

    def close(self):
        self.desired = False
        self.closed = True
        try: self.shutdown()
        except (requests.RequestException, RuntimeError): pass
        self.wake.set()
