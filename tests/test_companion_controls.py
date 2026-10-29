import threading

import pytest
import requests

from screenmate.core import Engine
from screenmate.server import create_server


def test_cosmetic_settings_do_not_invalidate_or_trigger_capture(tmp_path):
    from PIL import Image
    engine = Engine(tmp_path, capture=lambda box: Image.new("RGB", (20, 20)))
    engine.set_enabled(True)
    engine.sample()
    generation = engine.generation
    engine.wake.clear()
    engine.configure({"pet_size": 250, "activity": "lively", "bubbles": False})
    assert engine.latest() is not None
    assert engine.generation == generation
    assert not engine.wake.is_set()


@pytest.mark.parametrize("settings", [{"pet_size": 99}, {"pet_size": 401}, {"activity": "chaos"},
    {"bubbles": "false"}, {"reduced_motion": 1}, {"voice_style": "unknown"}, {"voice_url": "file:///private"}])
def test_bad_appearance_settings_are_atomic(tmp_path, settings):
    engine = Engine(tmp_path)
    before = dict(engine.config)
    with pytest.raises(ValueError):
        engine.configure(settings)
    assert engine.config == before


def test_actions_and_connection_status_auth_and_secret_redaction(tmp_path):
    engine = Engine(tmp_path)
    engine.configure({"voice_key": "test-secret-never-returned"})
    server = create_server(engine, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = requests.Session()
    session.trust_env = False
    base = f"http://127.0.0.1:{server.server_port}"
    headers = {"Authorization": "Bearer " + engine.config["token"]}
    try:
        assert session.post(base+"/v1/pet/action", json={"pose": "eat"}).status_code == 401
        assert session.post(base+"/v1/pet/action", headers=headers, json={"pose": "eat"}).status_code == 200
        assert engine.pet_commands.pop() == "eat"
        assert session.post(base+"/v1/pet/action", headers=headers, json={"pose": "unknown"}).status_code == 400
        assert session.post(base+"/v1/bridge/heartbeat", headers=headers, json={"vision_configured": True}).status_code == 200
        status = session.get(base+"/v1/status", headers=headers)
        assert status.json()["bridge"]["connected_at"]
        assert "test-secret-never-returned" not in status.text
        assert engine.config["token"] not in status.text
        assert session.get(base+"/companion/../../runtime/settings.private.json").status_code != 200
    finally:
        session.close()
        server.shutdown()
        server.server_close()
