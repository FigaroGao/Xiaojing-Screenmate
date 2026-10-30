"""Small native desktop chat; no browser, screenshot or network action on typing."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class ChatBox(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.pending = None
        self.setWindowTitle('和小鲸说话')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(340)
        self.resize(390, 190)
        self.setStyleSheet('QWidget {background:#f5f9fc;color:#243e54;font-size:14px;} QLineEdit {background:white;padding:10px;border:1px solid #b9cfde;border-radius:8px;} QPushButton {padding:8px;background:#dbeef8;border-radius:8px;}')
        layout = QVBoxLayout(self)
        title = QLabel('和小鲸说话 · 暂停陪看也能聊')
        layout.addWidget(title)
        self.reply = QLabel('想说什么就打在下面吧')
        self.reply.setTextFormat(Qt.TextFormat.PlainText)
        self.reply.setWordWrap(True)
        self.reply.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reply.setMaximumHeight(150)
        layout.addWidget(self.reply)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText('输入消息，回车发送…')
        self.input.setMaxLength(2000)
        self.input.returnPressed.connect(self.submit)
        row.addWidget(self.input)
        button = QPushButton('发送')
        button.clicked.connect(self.submit)
        row.addWidget(button)
        layout.addLayout(row)
        self.status = QLabel('不会因为打字开启截图')
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

    def submit(self):
        text = self.input.text().strip()
        if not text:return
        try:
            self.pending = self.engine.submit_chat(text)
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.input.clear()
        self.status.setText('已排队，等待小鲸回复')

    def refresh(self):
        with self.engine.lock:
            reply = dict(self.engine.reply) if self.engine.reply else None
            receipt = self.engine.chat_receipts.get(self.pending)
        if reply:
            self.reply.setText(reply['text'][:500])
            self.reply.setToolTip(reply['text'])
        if self.pending:
            self.status.setText({'queued':'已排队，等待平板连接','dispatched':'小鲸正在回复…',
                                 'replied':'小鲸已回复','cancelled':'已取消'}.get(receipt,'没有回执，请检查连接'))

    def open_near(self, rect):
        self.adjustSize()
        screen = self.screen().availableGeometry()
        x = max(screen.left(), min(rect.right()-self.width(), screen.right()-self.width()))
        y = rect.top()-self.height()-12
        if y < screen.top():y = min(rect.bottom()+12, screen.bottom()-self.height())
        self.move(x,y)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
