"""Coopanion's unmodified rig hosted in a transparent native Qt WebEngine window."""
import json
import math
import subprocess
import time

from PySide6.QtCore import QObject, QSharedMemory, QTimer, Qt, QUrl, QRect, Slot, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QRegion, QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineUrlRequestInterceptor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .coopanion import SOURCE, REVISION, WEB, ACTIONS, hit_test, transfer_delta
from .desktop import WindowIntegration
from .panel import ControlPanel, LocalPage


class LocalRequests(QWebEngineUrlRequestInterceptor):
    def __init__(self, origin, parent):
        super().__init__(parent)
        self.origin = QUrl(origin)

    def interceptRequest(self, info):
        url = info.requestUrl()
        local = (url.scheme(), url.host(), url.port()) == (self.origin.scheme(), self.origin.host(), self.origin.port())
        if not local and url.scheme() not in ("qrc", "data", "blob"):
            info.block(True)


class RendererBridge(QObject):
    state = Signal(str)
    action = Signal(str)
    pointer = Signal(str)
    transfer = Signal(str)
    home = Signal()

    def __init__(self, owner):
        super().__init__(owner.widget)
        self.owner = owner

    @Slot(result=str)
    def initial(self):
        payload = self.owner.payload()
        payload["position"] = self.owner.position
        return json.dumps(payload, ensure_ascii=False)

    @Slot()
    def ready(self):
        self.owner.ready = True
        self.owner.widget.show()
        self.owner.widget.setWindowOpacity(1)
        self.owner.capture_excluded = self.owner.integration.exclude()
        self.owner.engine.pet_state.update(ready=True, error="", renderer="coopanion")

    @Slot(str)
    def report(self, value):
        self.owner.report(value)

    @Slot(str)
    def failed(self, error):
        self.owner.ready = False
        self.owner.integration.passthrough(True)
        self.owner.engine.pet_state = {"ready": False, "renderer": "coopanion", "pose": "neutral", "label": "渲染失败", "error": "动态模型暂时无法加载，可使用兼容模式"}
        self.owner.widget.hide()

    @Slot()
    def openPanel(self):
        self.owner.open_panel()

    @Slot()
    def menu(self):
        self.owner.menu.popup(QCursor.pos())

    @Slot(int)
    def resizePet(self, delta):
        self.owner.engine.configure({"pet_size": max(100, min(400, self.owner.engine.config["pet_size"]+delta))})


class Pet:
    def __init__(self, engine, voice, url, instance_key="xiaojing-screenmate-pet"):
        if not (WEB / "whale/figure.js").is_file():
            raise RuntimeError("请先运行 python tools/setup_pet.py 安装动态模型")
        actual = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
        if actual != REVISION:
            raise RuntimeError("动态模型版本不同，请先检查；不自动覆盖")
        if QApplication.instance() is None:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        self.app = QApplication.instance() or QApplication([])
        self.singleton = QSharedMemory(instance_key)
        if not self.singleton.create(1):
            raise RuntimeError("小鲸桌宠已经运行")
        self.app.setQuitOnLastWindowClosed(False)
        self.engine, self.voice, self.url = engine, voice, url
        self.ready = False
        self.panel = None
        self.layout = {}
        self.position_path = engine.root / "companion-position.private.json"
        self.position = {}
        try:
            saved = json.loads(self.position_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        self.screen = next((s for s in self.app.screens() if s.name()==saved.get("screen")), self.app.primaryScreen())
        if saved.get("screen") == self.screen.name():
            if all(isinstance(saved.get(k), (int, float)) and math.isfinite(saved[k]) for k in ("x", "y")):
                self.position = {k: saved[k] for k in ("x", "y")}
        self.widget = QWebEngineView()
        self.widget.setWindowTitle("小鲸 · 动态桌宠")
        self.widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.widget.setGeometry(self.screen.availableGeometry())
        self.widget.setMask(QRegion(QRect(0, 0, 1, 1)))
        self.profile = QWebEngineProfile(self.widget)  # off-the-record; no persisted cookies or browsing history
        self.interceptor = LocalRequests(url, self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.page = LocalPage(url, self.profile)
        self.page.setBackgroundColor(QColor(0, 0, 0, 0))
        self.widget.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = RendererBridge(self)
        self.channel.registerObject("host", self.bridge)
        self.page.setWebChannel(self.channel)
        self.integration = WindowIntegration(self.widget)
        # A zero-opacity WebEngine window may suspend requestAnimationFrame before ready.
        # Transparent page + a tiny initial mask keep the desktop unobstructed while it loads.
        self.widget.setWindowOpacity(1)
        self.widget.show()
        self.integration.passthrough(True)
        self.capture_excluded = self.integration.exclude()
        self.last_payload = None
        self.last_reply = None
        self.last_save = 0
        self.last_position = None
        self.refresh_at = 0
        self.menu = QMenu()
        self.menu.addAction("打开小鲸的小窝", self.open_panel)
        self.menu.addAction("开启持续陪看", lambda: engine.set_enabled(True))
        self.menu.addAction("暂停观看", lambda: engine.set_enabled(False))
        self.menu.addSeparator()
        self.menu.addAction("让小鲸回到屏幕上", self.reset_position)
        self.menu.addAction("显示 / 隐藏桌宠", self.toggle_visible)
        self.menu.addAction("停止说话", voice.stop)
        self.menu.addAction("复制配对码", lambda: self.app.clipboard().setText(engine.config["token"]))
        self.menu.addSeparator()
        self.menu.addAction("退出", self.app.quit)
        icon = QIcon(str(WEB / "whale/thumbs/deepseek.png"))
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip("小鲸 · 动态鲸鱼娘")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda reason: self.open_panel() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        self.app.screenRemoved.connect(lambda _: QTimer.singleShot(0, self.rehome))
        self.app.screenAdded.connect(lambda s: s.availableGeometryChanged.connect(lambda _: self.rehome()))
        for screen in self.app.screens():
            screen.availableGeometryChanged.connect(lambda _: self.rehome())
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(20)
        self.app.aboutToQuit.connect(voice.stop)
        self.widget.load(QUrl(url+"/renderer"))
        engine.pet_state = {"ready": False, "renderer": "coopanion", "pose": "neutral", "label": "正在载入", "error": ""}
        QTimer.singleShot(30000, lambda: self.bridge.failed("Renderer did not become ready") if not self.ready else None)

    def payload(self):
        config = self.engine.config
        status = self.engine.status()
        phase = status["bridge"].get("phase")
        return {k: config[k] for k in ("pet_size", "activity", "reduced_motion", "bubbles", "pet_scheme", "pet_outfit", "render_fps")} | {
            "thinking": phase in ("analyzing", "chat") and time.time()-status["bridge"].get("connected_at", 0)<120,
            "speaking": self.voice.speaking, "mouth": self.voice.mouth_level(), "reply": status["reply"]}

    def report(self, value):
        if len(value)>20000:
            return
        try:
            data = json.loads(value)
            box = data["box"]
            if not all(isinstance(box.get(k), (int,float)) and math.isfinite(box[k]) and abs(box[k])<100000 for k in ("x","y","w","h")):
                return
            if len(data.get("hit", []))>20:
                return
            region = QRegion(QRect(math.floor(box["x"])-40, math.floor(box["y"])-60, max(1,math.ceil(box["w"])+80), max(1,math.ceil(box["h"])+100)))
            bubble = data.get("bubbleRect")
            if bubble:
                region |= QRegion(QRect(int(bubble["x"]), int(bubble["y"]), int(bubble["w"]), int(bubble["h"])))
            self.widget.setMask(region)
            self.layout = data
            action = data.get("action") or "neutral"
            mode = data.get("mode", "idle")
            label = ACTIONS.get(action, "陪伴") if action!="neutral" else {"idle":"待机","walk":"散步","run":"跑步","drag":"被拎起","air":"落下","sleep":"小憩","sit":"坐下"}.get(mode,"活动中")
            self.engine.pet_state.update(ready=self.ready, renderer="coopanion", pose=action, label=label, phase=mode, capture_excluded=self.capture_excluded, error="")
            if not data.get("pressing") and not data.get("moving") and time.monotonic()-self.last_save>2:
                position = {"screen": self.screen.name(), "x": round(data["x"], 2), "y": round(data.get("y", self.widget.height()-8), 2)}
                if position != self.last_position:
                    tmp = self.position_path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(position), encoding="utf-8")
                    tmp.replace(self.position_path)
                    self.last_position = position
                self.last_save = time.monotonic()
        except (ValueError, TypeError, KeyError, OSError):
            return

    def refresh(self):
        if not self.ready:
            return
        cursor = QCursor.pos()
        pressing = self.layout.get("pressing", False)
        down = bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        if pressing:
            target = self.app.screenAt(cursor)
            if target and target != self.screen:
                old = self.widget.geometry().topLeft()
                self.screen = target
                self.widget.setGeometry(target.availableGeometry())
                new = self.widget.geometry().topLeft()
                dx,dy = transfer_delta((old.x(),old.y()),(new.x(),new.y()))
                self.bridge.transfer.emit(json.dumps({"dx": dx,"dy":dy}))
                self.capture_excluded = self.integration.exclude()
            point = self.widget.mapFromGlobal(cursor)
            self.bridge.pointer.emit(json.dumps({"x":point.x(),"y":point.y(),"down":down}))
        point = self.widget.mapFromGlobal(cursor)
        transparent = self.engine.config["input_passthrough"] and not pressing and not hit_test(self.layout,point.x(),point.y())
        self.integration.passthrough(transparent)
        now = time.monotonic()
        if now < self.refresh_at:
            return
        self.refresh_at = now+.08
        with self.engine.lock:
            command = self.engine.pet_commands.popleft() if self.engine.pet_commands else None
            speech = self.engine.voice_commands.popleft() if self.engine.voice_commands else None
        if speech:
            self.voice.say(speech)
        if command:
            self.bridge.action.emit(command)
        reply = self.engine.reply
        if reply and reply["at"] != self.last_reply:
            self.last_reply = reply["at"]
            if self.engine.config.get("voice_key"):
                self.voice.say(reply["text"])
        payload = json.dumps(self.payload(), ensure_ascii=False)
        self.engine.pet_state.update(speaking=self.voice.speaking,mouth=self.voice.mouth_level())
        if self.voice.error:
            self.engine.voice_status = {"checked":True,"available":False,"message":self.voice.error}
        elif self.voice.generating:
            self.engine.voice_status = {"checked":True,"available":True,"message":"正在本地合成语音，首次加载需要一些时间…"}
        elif self.voice.speaking:
            self.engine.voice_status = {"checked":True,"available":True,"message":"正在播放本地语音"}
        elif self.engine.voice_status.get("message") in ("正在播放本地语音", "正在本地合成语音，首次加载需要一些时间…"):
            self.engine.voice_status = {"checked":True,"available":True,"message":"本地语音播放完成"}
        if payload != self.last_payload:
            self.last_payload = payload
            self.bridge.state.emit(payload)

    def open_panel(self):
        if self.panel is None:
            self.panel = ControlPanel(self.url,self.engine.config["token"])
        self.panel.showNormal()
        self.panel.raise_()
        self.panel.activateWindow()

    def reset_position(self):
        self.screen = self.app.primaryScreen()
        self.widget.setGeometry(self.screen.availableGeometry())
        self.widget.show()
        self.bridge.home.emit()
        self.capture_excluded = self.integration.exclude()

    def rehome(self):
        if self.screen not in self.app.screens():
            self.screen = self.app.primaryScreen()
        self.widget.setGeometry(self.screen.availableGeometry())
        self.bridge.home.emit()
        self.capture_excluded = self.integration.exclude()

    def toggle_visible(self):
        self.widget.setVisible(not self.widget.isVisible())
        if self.widget.isVisible():
            self.capture_excluded = self.integration.exclude()

    def run(self):
        self.app.exec()
