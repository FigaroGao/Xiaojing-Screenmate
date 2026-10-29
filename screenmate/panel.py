"""Native settings window hosting the same local control page as the browser."""
import json

from PySide6.QtCore import QUrl
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow


class LocalPage(QWebEnginePage):
    def __init__(self, origin, parent):
        super().__init__(parent)
        self.origin = QUrl(origin)

    def acceptNavigationRequest(self, url, kind, main_frame):
        return (url.scheme(), url.host(), url.port()) == (self.origin.scheme(), self.origin.host(), self.origin.port())


class ControlPanel(QMainWindow):
    def __init__(self, url, token):
        super().__init__()
        self.setWindowTitle("小鲸的小窝 · Screenmate")
        self.resize(1120, 790)
        self.setMinimumSize(860, 640)
        self.web = QWebEngineView(self)
        self.web.setPage(LocalPage(url, self.web))
        self.setCentralWidget(self.web)
        self.web.loadFinished.connect(lambda ok: self.web.page().runJavaScript(
            "window.Desktop && window.Desktop.connect(" + json.dumps(token) + ")") if ok else None)
        self.web.load(QUrl(url))
        self.reload_shortcut = QShortcut(QKeySequence.StandardKey.Refresh, self)
        self.reload_shortcut.activated.connect(self.web.reload)

    def closeEvent(self, event: QCloseEvent):
        self.hide()
        event.ignore()
