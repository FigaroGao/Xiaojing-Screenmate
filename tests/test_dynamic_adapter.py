import threading

import requests

from screenmate.coopanion import hit_test, transfer_delta
from screenmate.core import Engine
from screenmate.server import create_server
from screenmate.voice import FeiyuVoice


def test_transparent_corners_and_bubble_keep_their_own_hit_regions():
    layout = {"hit": [{"x": 100, "y": 100, "r": 20}],
              "bubbleRect": {"x": 50, "y": 20, "w": 100, "h": 30}}
    assert hit_test(layout, 100, 100)
    assert hit_test(layout, 60, 25)
    assert not hit_test(layout, 80, 80)
    assert transfer_delta((0, 0), (-1920, -1080)) == (1920, 1080)
    assert transfer_delta((-1920, 0), (0, 0)) == (-1920, 0)


def test_pcm_envelope_tracks_audio_and_silence():
    from array import array
    samples = array('h', [0]*1200 + [10000]*1200).tobytes()
    levels = FeiyuVoice.pcm_envelope(samples, 2, 1, 24000)
    assert levels[0] == 0
    assert levels[1] > .9


def test_renderer_mime_private_paths_and_audition_readiness(tmp_path):
    engine = Engine(tmp_path)
    server = create_server(engine, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    session = requests.Session()
    session.trust_env = False
    base = f"http://127.0.0.1:{server.server_port}"
    auth = {"Authorization": "Bearer " + engine.config["token"]}
    try:
        assert session.get(base+'/renderer.js').headers['Content-Type'].startswith('text/javascript')
        assert session.get(base+'/coopanion/%2e%2e/settings.private.json').status_code != 200
        assert session.post(base+'/v1/voice/preview', json={}).status_code == 401
        assert session.post(base+'/v1/voice/preview', headers=auth, json={}).status_code == 400
        engine.pet_state['ready'] = True
        engine.configure({'voice_key':'local-test'})
        assert session.post(base+'/v1/voice/preview', headers=auth, json={}).status_code == 200
        assert len(engine.voice_commands) == 1
    finally:
        session.close()
        server.shutdown()
        server.server_close()
