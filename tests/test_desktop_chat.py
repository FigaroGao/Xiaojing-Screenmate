import pytest
from screenmate.core import Engine

def test_paused_chat_works_without_capture_and_is_not_replayed(tmp_path):
    e=Engine(tmp_path,capture=lambda _:pytest.fail('chat must not capture'))
    ident=e.submit_chat('你好小鲸')
    job=e.take_chat()
    assert job['id']==ident and e.take_chat() is None
    e.desktop_reply('你好呀',job['session'],ident)
    assert not e.enabled and e.latest() is None and e.reply['text']=='你好呀'
    assert e.chat_receipts[ident]=='replied'
    with pytest.raises(ValueError):e.desktop_reply('旧会话回复','invalid',ident)

def test_queue_bounds_and_unknown_reply_rejected(tmp_path):
    e=Engine(tmp_path)
    for i in range(16):e.submit_chat(str(i))
    with pytest.raises(ValueError):e.submit_chat('overflow')
    with pytest.raises(ValueError):e.desktop_reply('冒用回执',e.session,'unknown')
    with pytest.raises(ValueError):e.submit_chat('')

def test_pause_cancels_initiative_but_preserves_user_input(tmp_path):
    e=Engine(tmp_path)
    e.set_enabled(True)
    auto=e.submit_chat('主动观察',initiative=True,generation=e.generation)
    manual=e.submit_chat('主人消息')
    e.set_enabled(False)
    assert e.take_chat()['id']==manual
    assert e.chat_receipts[auto]=='cancelled'
    with pytest.raises(ValueError):e.submit_chat('旧观察',initiative=True,generation=e.generation)

def test_pause_rejects_already_dispatched_initiative_reply(tmp_path):
    e=Engine(tmp_path)
    e.set_enabled(True)
    ident=e.submit_chat('观察',initiative=True,generation=e.generation)
    job=e.take_chat()
    e.set_enabled(False)
    with pytest.raises(ValueError):e.desktop_reply('旧观察回复',job['session'],ident)
    assert e.reply is None and e.chat_receipts[ident]=='cancelled'
