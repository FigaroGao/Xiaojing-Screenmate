import threading
import pytest
from screenmate.core import Engine

def test_paused_does_not_enumerate(tmp_path,monkeypatch):
    import screenmate.desktop_info as info
    monkeypatch.setattr(info,'collect_desktop',lambda:pytest.fail('paused must not enumerate'))
    with pytest.raises(ValueError):Engine(tmp_path).desktop_info()

def test_pause_during_enumeration_discards_result(tmp_path,monkeypatch):
    import screenmate.desktop_info as info
    e=Engine(tmp_path);e.set_enabled(True)
    def collect():
        e.set_enabled(False)
        return {'windows':[{'title':'stale'}]}
    monkeypatch.setattr(info,'collect_desktop',collect)
    with pytest.raises(ValueError):e.desktop_info()

def test_current_windows_returned_only_when_enabled(tmp_path,monkeypatch):
    import screenmate.desktop_info as info
    monkeypatch.setattr(info,'collect_desktop',lambda:{'available':True,'windows':[{'app':'example.exe','foreground':True}]})
    e=Engine(tmp_path);e.set_enabled(True)
    assert e.desktop_info()['windows'][0]['foreground'] is True
