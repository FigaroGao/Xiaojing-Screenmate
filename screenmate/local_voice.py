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
        if engine.config.get("voice_url", "").rstrip("/") != "http://127.0.0.1:9880" or engine.config.get("voice_key") != key:
            return
        session = requests.Session()
        session.trust_env = False
        try:
            session.get("http://127.0.0.1:9880/v1/capabilities", timeout=1,
                        headers={"Authorization": "Bearer " + key})
            return  # Any existing listener belongs to its current owner.
        except requests.ConnectionError:
            pass
        except requests.RequestException:
            return
        finally:
            session.close()
        with (server / ".runtime/voice-service/launcher.log").open("ab") as log:
            subprocess.Popen([str(python), "-m", "feiyu_voice_service", "--config", str(config),
                              "--host", "127.0.0.1", "--port", "9880"], cwd=server,
                             stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    threading.Thread(target=start, daemon=True).start()
