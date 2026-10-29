import threading
import time

import pytest
import requests
from PIL import Image

from screenmate.core import Engine
from screenmate.server import create_server


@pytest.fixture
def engine(tmp_path):
    return Engine(tmp_path, capture=lambda bbox: Image.new("RGB", (80, 50), "navy"))


def test_no_capture_before_start(engine):
    engine.capture = lambda bbox: pytest.fail("paused capture")
    engine.sample()
    assert engine.latest() is None


def test_capture_does_not_write_screenshot(engine):
    engine.set_enabled(True)
    engine.sample()
    assert engine.latest()["image_base64"]
    assert list(engine.root.iterdir()) == [engine.path]


def test_pause_erases_frame_and_rejects_reply(engine):
    engine.set_enabled(True)
    engine.sample()
    engine.set_enabled(False)
    assert engine.latest() is None
    with pytest.raises(ValueError):
        engine.publish_reply("old", 1)


def test_inflight_capture_cannot_reappear_after_pause(engine):
    entered, release = threading.Event(), threading.Event()
    def capture(bbox):
        entered.set()
        release.wait(2)
        return Image.new("RGB", (20, 20))
    engine.capture = capture
    engine.set_enabled(True)
    worker = threading.Thread(target=engine.sample)
    worker.start()
    assert entered.wait(1)
    engine.set_enabled(False)
    engine.set_enabled(True)
    release.set()
    worker.join(2)
    assert engine.latest() is None


def test_duplicate_capture_skipped(engine):
    engine.set_enabled(True)
    engine.sample()
    engine.sample()
    assert engine.sequence == 1
    engine.configure({"skip_unchanged": False})
    engine.sample()
    engine.sample()
    assert engine.sequence == 3


def test_text_mode_never_captures(engine):
    engine.configure({"mode": "text"})
    engine.capture = lambda bbox: pytest.fail("text mode captured an image")
    engine.set_enabled(True)
    engine.ingest_text({"title": "ARG", "text": "线索 42"})
    engine.sample()
    assert engine.latest()["image_base64"] is None
    assert engine.latest()["text"]["text"] == "线索 42"


def test_stale_text_not_reused(engine):
    engine.configure({"mode": "text"})
    engine.set_enabled(True)
    engine.ingest_text({"text": "old"})
    engine.text["received_at"] -= 100
    engine.sample()
    assert engine.latest() is None
    assert engine.error


def test_unchanged_screen_refreshes_freshness_without_new_analysis(engine):
    engine.set_enabled(True)
    engine.sample()
    engine.observation["captured_at"] -= 100
    assert engine.latest() is None
    engine.sample()
    assert engine.sequence == 1
    assert engine.latest() is not None


def test_failure_invalidates_old_frame(engine):
    engine.set_enabled(True)
    engine.sample()
    def fail(bbox):
        raise RuntimeError("locked")
    engine.capture = fail
    engine.sample()
    assert engine.latest() is None
    assert engine.error == "locked"


def test_expired_frame_not_served(engine):
    engine.set_enabled(True)
    engine.sample()
    engine.observation["captured_at"] -= 100
    assert engine.latest() is None


def test_slow_reply_allowed_when_new_frame_arrives(engine):
    engine.configure({"skip_unchanged": False})
    engine.set_enabled(True)
    engine.sample()
    engine.sample()
    engine.publish_reply("I saw frame one", 1)
    assert engine.reply["observation_id"] == 1


@pytest.mark.parametrize("values", [{"interval": 0}, {"interval": 3601}, {"mode": "bad"},
    {"monitor_bbox": [0, 0, 0, 30]}, {"monitor_bbox": [1, 2]}, {"monitor_bbox": [0, 0, 2.5, 3]}])
def test_invalid_config_rejected(engine, values):
    with pytest.raises(ValueError):
        engine.configure(values)


def test_config_roundtrip_but_start_paused(engine):
    engine.configure({"interval": 7, "mode": "text"})
    engine.set_enabled(True)
    restarted = Engine(engine.root)
    assert restarted.config["interval"] == 7
    assert restarted.config["token"] == engine.config["token"]
    assert not restarted.enabled


def test_http_auth_pause_and_reply(engine):
    server = create_server(engine, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    headers = {"Authorization": "Bearer " + engine.config["token"]}
    session = requests.Session()
    session.trust_env = False
    try:
        assert session.get(url + "/v1/status").status_code == 401
        assert session.post(url + "/v1/watching", json={"enabled": True}).status_code == 401
        assert session.get(url + "/", headers=headers).status_code == 200
        assert session.post(url + "/v1/watching", headers=headers, json={"enabled": True}).status_code == 200
        engine.sample()
        assert session.get(url + "/v1/observations/latest", headers=headers).json()["observation"]
        assert session.post(url + "/v1/watching", headers=headers, json={"enabled": False}).status_code == 200
        assert session.get(url + "/v1/observations/latest", headers=headers).json()["observation"] is None
        assert session.post(url + "/v1/replies", headers=headers, json={"text": "late", "observation_id": 1}).status_code == 400
        assert session.post(url + "/v1/watching", headers=headers, json={"enabled": "false"}).status_code == 400
    finally:
        session.close()
        server.shutdown()
        server.server_close()
