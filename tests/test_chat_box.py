import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from screenmate.chat_box import ChatBox
from screenmate.core import Engine

def test_native_chat_queues_once_without_capture(tmp_path):
    app=QApplication.instance() or QApplication([])
    engine=Engine(tmp_path,capture=lambda _: (_ for _ in ()).throw(AssertionError('must not capture')))
    box=ChatBox(engine)
    box.input.setText('你好，小鲸')
    box.submit();box.submit()
    job=engine.take_chat()
    assert job['text']=='你好，小鲸' and engine.take_chat() is None
    assert not engine.enabled
    engine.desktop_reply('你好呀',job['session'],job['id'])
    box.refresh()
    assert box.reply.text()=='你好呀' and box.status.text()=='小鲸已回复'
    box.timer.stop();box.deleteLater();app.processEvents()

def test_native_chat_keeps_unsent_text_on_queue_failure(tmp_path):
    app=QApplication.instance() or QApplication([])
    engine=Engine(tmp_path)
    for i in range(16):engine.submit_chat(str(i))
    box=ChatBox(engine);box.input.setText('别丢掉')
    box.submit()
    assert box.input.text()=='别丢掉' and '满' in box.status.text()
    box.timer.stop();box.deleteLater();app.processEvents()
