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
            subprocess.Popen(command, cwd=server,
                             stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    threading.Thread(target=start, daemon=True).start()
