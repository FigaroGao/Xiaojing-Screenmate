import pytest
from screenmate.core import Engine
from screenmate.voice_bank import PHRASES,catalog,audio_path

def test_bank_rejects_paths_and_lists_only_installed_files(tmp_path):
    folder=tmp_path/'voice-bank';folder.mkdir()
    (folder/'here.wav').write_bytes(b'test fixture')
    assert catalog(tmp_path)[0]['id']=='here'
    assert catalog(tmp_path)[0]['automatic'] is False
    with pytest.raises(ValueError):audio_path(tmp_path,'../settings.private.json')
    with pytest.raises(ValueError):audio_path(tmp_path,'quiet')

def test_presence_clip_requires_live_generation_and_cools_down(tmp_path):
    e=Engine(tmp_path)
    folder=tmp_path/'voice-bank';folder.mkdir();(folder/'here.wav').write_bytes(b'fixture')
    with pytest.raises(ValueError):e.cached_voice('here',e.generation)
    e.set_enabled(True)
    with pytest.raises(ValueError):e.cached_voice('here',e.generation-1)
    e.cached_voice('here',e.generation)
    assert e.voice_commands[-1]=={'cached':'here','generation':e.generation}
    with pytest.raises(ValueError):e.cached_voice('here',e.generation)
    e.set_enabled(False)
    assert e.voice_commands[-1]['generation']!=e.generation
