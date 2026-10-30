import io,zipfile,sqlite3,threading
import requests
from screenmate.core import Engine
from screenmate.server import create_server
from screenmate.sessions import Sessions

def test_session_schema_upgrade_and_summary_cache_are_non_destructive(tmp_path):
    path=tmp_path/'old.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,started REAL,ended REAL,last_seen REAL,reason TEXT,ack TEXT)')
        db.execute("INSERT INTO sessions VALUES('old',10,20,20,'paused','251')")
    s=Sessions(path)
    assert s.missing_summaries()==['old']
    s.acknowledge('old',251,'带日期的总结')
    s.acknowledge('old',251)
    assert s.recent()[0]['summary']=='带日期的总结'
    assert not s.missing_summaries()
    assert s.recent()[0]['started']==10

def test_ui_endpoints_require_auth_and_manual_audition_does_not_enable_capture(tmp_path):
    e=Engine(tmp_path);folder=tmp_path/'voice-bank';folder.mkdir();(folder/'here.wav').write_bytes(b'fixture')
    e.pet_state['ready']=True
    server=create_server(e,port=0);threading.Thread(target=server.serve_forever,daemon=True).start()
    http=requests.Session();http.trust_env=False
    base=f'http://127.0.0.1:{server.server_port}'
    headers={'Authorization':'Bearer '+e.config['token']}
    try:
        for route in ('/v1/sessions','/v1/extension/download'):
            assert http.get(base+route).status_code==401
        r=http.get(base+'/v1/extension/download',headers=headers)
        assert r.status_code==200 and r.headers['Content-Type']=='application/zip'
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            assert 'xiaojing-browser-extension/manifest.json' in z.namelist()
            assert all('runtime' not in name and 'private' not in name for name in z.namelist())
        assert http.post(base+'/v1/voice/bank/preview',headers=headers,json={'id':'here'}).status_code==200
        assert not e.enabled and e.voice_commands[-1]['preview'] is True
        assert http.post(base+'/v1/voice/bank/preview',headers=headers,json={'id':'../settings.private.json'}).status_code==400
        http.post(base+'/v1/voice/stop',headers=headers,json={})
        assert list(e.voice_commands)==[{'stop':True}]
    finally:http.close();server.shutdown();server.server_close()
