import time
from types import SimpleNamespace
from screenmate.core import Engine
from screenmate.local_voice import VoiceControl
from screenmate.pet import Pet
from screenmate.voice import FeiyuVoice


def until(predicate):
    deadline=time.monotonic()+3
    while not predicate():
        assert time.monotonic()<deadline
        time.sleep(.01)


def test_opt_in_loading_cancel_and_retry_do_not_enable_capture(tmp_path,monkeypatch):
    e=Engine(tmp_path)
    launches=[]; stops=[]
    monkeypatch.setattr('screenmate.local_voice.start_installed_voice',lambda engine: launches.append(True))
    monkeypatch.setattr(VoiceControl,'shutdown',lambda self: stops.append(True))
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'tts':[{'available':ready[0]}]}
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,*args,**kwargs):return Response()
    ready=[False]
    monkeypatch.setattr('screenmate.local_voice.requests.Session',Session)
    c=VoiceControl(e)
    assert c.engine.voice_status['state']=='off' and not launches
    c.toggle(True)
    until(lambda:bool(launches))
    assert e.voice_status['state']=='loading' and not e.enabled
    c.toggle(False)
    until(lambda:e.voice_status['state']=='off')
    assert stops and not e.enabled
    ready[0]=True
    c.toggle(True)
    until(lambda:e.voice_status['state']=='ready')
    assert not e.enabled
    c.close()


def test_bubble_waits_for_matching_audio_but_text_survives_disabled_or_failure():
    pet=SimpleNamespace(engine=SimpleNamespace(reply={'at':12,'text':'hello'},voice_status={'state':'ready'}),
                        voice=SimpleNamespace(error='',playing_key=None))
    assert Pet.bubble_reply(pet) is None
    pet.voice.playing_key=11
    assert Pet.bubble_reply(pet) is None
    pet.voice.playing_key=12
    assert Pet.bubble_reply(pet)['text']=='hello'
    pet.voice.playing_key=None;pet.voice.error='failed'
    assert Pet.bubble_reply(pet)['text']=='hello'
    pet.voice.error='';pet.engine.voice_status['state']='loading'
    assert Pet.bubble_reply(pet)['text']=='hello'


def test_pcm_playback_publishes_corresponding_text_only_at_audio_start(monkeypatch):
    import io,wave,sys
    stream=io.BytesIO()
    with wave.open(stream,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*1600)
    audio=stream.getvalue()
    class Response:
        status_code=200
        def __init__(self,path):self.path=path
        def json(self):return {'id':'a'*32} if self.path.endswith('/speech') else {'status':'success'}
        def iter_content(self,*args):yield audio
    class Session:
        headers={}
        def request(self,method,url,**kw):
            assert voice.playing_key is None
            return Response(url)
        def close(self):pass
    voice=FeiyuVoice({'voice_key':'test','voice_url':'http://127.0.0.1:9881','voice_style':'cute'})
    played=[]
    def play(data,flags):
        assert voice.speaking and voice.playing_key==42 and voice.playing_text=='test text'
        played.append(data)
    monkeypatch.setattr('screenmate.voice.requests.Session',Session)
    monkeypatch.setitem(sys.modules,'winsound',SimpleNamespace(PlaySound=play,SND_MEMORY=4))
    voice._work('test text',voice.generation,42)
    assert played==[audio] and not voice.speaking and not voice.error
