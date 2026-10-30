"""Connect this checkout to its verified, separately installed Feiyu runtime."""
import json
from pathlib import Path
import shutil
import subprocess
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "runtime/feiyu-voice/server"


def main():
    runtime = ROOT / "runtime/voice-linux/tts"
    diagnostic = json.loads((runtime / "diagnostic.json").read_text(encoding="utf-8"))
    if diagnostic.get("status") != "success":
        raise RuntimeError("Run and pass the official runtime diagnostic first")
    shutil.copyfile(runtime / "runtime.local.json", SERVER / "configs/runtime.tts.cuda.local.json")
    config = {"schema":"feiyu-voice-service-v1", "data_dir":".runtime/voice-service",
              "max_queue":16,"max_upload_mb":128,"tts":{"feiyu":{
                  "engine":"cosyvoice3_release","package":"models/FeiyuVoice-CosyVoice3",
                  "runtime_profile":"configs/runtime.tts.cuda.local.json"}},"rvc":{},"singing":None}
    config_path = SERVER / "configs/voice_service.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    session = requests.Session()
    session.trust_env = False
    try:
        session.get("http://127.0.0.1:9880/v1/capabilities",timeout=1)
    except requests.ConnectionError:
        with (ROOT / "runtime/voice-service.log").open("ab") as log:
            subprocess.Popen([str(SERVER / ".venv/Scripts/pythonw.exe"), "-m", "feiyu_voice_service",
                              "--config",str(config_path),"--host","127.0.0.1","--port","9880"],
                             cwd=SERVER,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    key_path = SERVER / ".runtime/voice-service/api_key.txt"
    deadline = time.monotonic()+120
    while time.monotonic()<deadline:
        if key_path.is_file():
            key = key_path.read_text(encoding="utf-8").strip()
            try:
                result = session.get("http://127.0.0.1:9880/v1/capabilities",
                                     headers={"Authorization":"Bearer "+key},timeout=3)
                result.raise_for_status()
                if not any(row.get("available") for row in result.json().get("tts",[])):
                    raise RuntimeError("Feiyu TTS configuration is unavailable")
                settings_path=ROOT / "runtime/settings.private.json"
                settings=json.loads(settings_path.read_text(encoding="utf-8"))
                headers={"Authorization":"Bearer "+settings['token']}
                response=session.post("http://127.0.0.1:17860/v1/settings",headers=headers,
                                      json={"voice_url":"http://127.0.0.1:9880","voice_key":key,
                                            "voice_style":"cute"},timeout=5)
                response.raise_for_status()
                print("Local Feiyu API connected. Actual synthesis still needs verification.")
                return
            except requests.RequestException:
                pass
        time.sleep(1)
    raise RuntimeError("Feiyu API did not become ready; inspect runtime/voice-service.log")


if __name__ == "__main__":
    main()
