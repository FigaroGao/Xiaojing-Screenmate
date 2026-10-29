import asyncio
import importlib.util
import io
import sys
import types
import wave
from pathlib import Path


def load_plugin(monkeypatch):
    api = types.ModuleType("astrbot.api")
    api.AstrBotConfig = dict
    api.logger = types.SimpleNamespace(warning=lambda *args: None)
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = object
    event.filter = types.SimpleNamespace(on_llm_request=lambda **kw: lambda f: f,
                                        on_llm_response=lambda **kw: lambda f: f)
    star = types.ModuleType("astrbot.api.star")
    class Star:
        def __init__(self, context):
            self.context = context
    star.Star, star.Context = Star, object
    star.register = lambda *args: lambda cls: cls
    for key, module in {"astrbot": types.ModuleType("astrbot"), "astrbot.api": api,
                         "astrbot.api.event": event, "astrbot.api.star": star}.items():
        monkeypatch.setitem(sys.modules, key, module)
    path = Path(__file__).resolve().parents[1] / "integrations/astrbot_plugin_xiaojing_screenmate/main.py"
    spec = importlib.util.spec_from_file_location("test_screenmate_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ScreenmatePlugin


def test_plugin_owner_isolation_and_pause_generation(monkeypatch):
    Plugin = load_plugin(monkeypatch)
    async def run():
        plugin = Plugin(None, dict(enabled=True, owner_id="owner"))
        plugin.latest = dict(id=1, captured_at=__import__('time').time(), session="session", generation=2, text="线索")
        async def request(*args, **kwargs):
            return {"observation": dict(session="session", generation=2)}
        plugin.request = request
        def event(sender, group):
            return types.SimpleNamespace(get_sender_id=lambda: sender, get_group_id=lambda: group)
        req = types.SimpleNamespace(prompt="hello")
        await plugin.attach_observation(event("other", ""), req)
        assert req.prompt == "hello"
        await plugin.attach_observation(event("owner", "group"), req)
        assert req.prompt == "hello"
        await plugin.attach_observation(event("owner", ""), req)
        assert "线索" in req.prompt
        plugin.latest["generation"] = 1
        req.prompt = "hello"
        await plugin.attach_observation(event("owner", ""), req)
        assert req.prompt == "hello"
        await plugin.terminate()
    asyncio.run(run())


def test_voice_uses_real_feiyu_job_contract(monkeypatch):
    from screenmate.voice import FeiyuVoice
    from screenmate.core import DEFAULTS
    import requests
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0" * 240)
    calls, played = [], []
    class Response:
        status_code = 200
        def __init__(self, data=None):
            self.data = data
        def json(self):
            return self.data
        def iter_content(self, size):
            yield out.getvalue()
    class Session:
        def __init__(self):
            self.headers = {}
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/v1/speech"):
                return Response({"id": "a" * 32})
            if url.endswith("/audio"):
                return Response()
            return Response({"status": "success"})
        def close(self):
            pass
    monkeypatch.setattr(requests, "Session", Session)
    monkeypatch.setitem(sys.modules, "winsound", types.SimpleNamespace(SND_MEMORY=4, PlaySound=lambda *args: played.append(args)))
    voice = FeiyuVoice(dict(DEFAULTS, voice_key="test-only"))
    voice._work("测试", voice.generation)
    assert calls[0][2]["json"] == {"voice": "feiyu", "text": "测试", "style": "cute"}
    assert calls[1][1].endswith("/v1/jobs/" + "a" * 32)
    assert played[0][0] == out.getvalue()
    assert not voice.error
