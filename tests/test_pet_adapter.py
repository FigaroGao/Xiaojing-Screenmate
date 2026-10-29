"""Offscreen smoke test against the actual, separately installed upstream renderer."""
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "runtime/dsh-co-pet/pet/pet_app.py").exists(),
                    reason="optional upstream desktop dependency is not installed in CI")
def test_existing_pet_renderer(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from screenmate.core import Engine
    from screenmate.voice import FeiyuVoice
    from screenmate.pet import Pet
    engine = Engine(tmp_path)
    pet = Pet(engine, FeiyuVoice(engine.config), "http://127.0.0.1:17860", instance_key="screenmate-test-" + __import__('uuid').uuid4().hex)
    try:
        assert pet.widget._pet is not None
        assert pet.widget._pixmaps
        engine.set_enabled(True)
        pet.refresh()
        assert pet.widget._model.phrase == "陪看中"
        engine.set_enabled(False)
        pet.refresh()
        assert pet.widget._model.phrase == "观看已暂停"
    finally:
        pet.timer.stop()
        pet.tray.hide()
        pet.widget._bubble.hide()
        pet.widget.hide()
        pet.singleton.detach()
