import importlib.util
from pathlib import Path
import threading

import requests


def test_resident_auth_loading_style_and_bounded_queue(tmp_path,monkeypatch):
    spec = importlib.util.spec_from_file_location('resident_voice', Path(__file__).parents[1]/'tools/resident_voice.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SERVER = tmp_path
    key_path = tmp_path/'.runtime/voice-service/api_key.txt'
    key_path.parent.mkdir(parents=True)
    key_path.write_text('private-test-key')
    resident = module.Resident()
    http = module.ThreadingHTTPServer(('127.0.0.1',0),module.handler(resident))
    threading.Thread(target=http.serve_forever,daemon=True).start()
    s = requests.Session()
    s.trust_env = False
    base = f'http://127.0.0.1:{http.server_port}'
    try:
        assert s.get(base+'/v1/capabilities').status_code == 401
        assert s.post(base+'/v1/shutdown').status_code == 401
        s.headers['Authorization'] = 'Bearer private-test-key'
        calls=[]
        class Timer:
            def __init__(self,delay,callback):calls.append((delay,callback))
            def start(self):pass
        monkeypatch.setattr(module.threading,'Timer',Timer)
        assert s.post(base+'/v1/shutdown').status_code == 200
        assert calls and not resident.ready  # Can cancel during model loading.
        assert s.post(base+'/v1/speech',json={'text':'hi'}).status_code == 503
        resident.ready = True
        assert s.post(base+'/v1/speech',json={'text':'hi','style':'gentle'}).status_code == 400
        for i in range(4):
            result=s.post(base+'/v1/speech',json={'text':'hi','style':'cute'})
            assert result.status_code == 202
        assert s.post(base+'/v1/speech',json={'text':'hi'}).status_code == 429
        assert len(resident.jobs) == 4
        job = result.json()['id']
        assert 'text' not in s.get(base+'/v1/jobs/'+job).json()
        assert s.get(base+'/v1/jobs/'+job+'/audio').status_code == 404
    finally:
        s.close()
        http.shutdown()
        http.server_close()
