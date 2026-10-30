"""Optional v0.2 sprite renderer, kept for explicit compatibility fallback."""
import ctypes
import random
import subprocess
import sys
import time
from pathlib import Path

from .companion_assets import CHIBI_REVISION, POSES, ROOT, load_companion

UPSTREAM_REVISION = "b394cdacca07526a36a36373cb11bec603b74651"


class Pet:
    def __init__(self, engine, voice, url, instance_key="xiaojing-screenmate-pet"):
        directory = ROOT / "runtime/dsh-co-pet"
        for source, revision in ((directory, UPSTREAM_REVISION), (ROOT / "runtime/chibi-dafeiyu", CHIBI_REVISION)):
            if not source.exists():
                raise RuntimeError("请先运行 python tools/setup_pet.py 安装现有桌宠与Q版素材")
            actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            if actual != revision:
                raise RuntimeError("桌宠依赖版本不同，请先检查；不自动覆盖")
        sys.path.insert(0, str(directory / "pet"))
        import pet_app as upstream
        import state_listener
        from pet_loader import Pet as AssetPet, pil_to_qimage
        from PySide6.QtCore import QSharedMemory, QTimer, Qt, QPoint, QPropertyAnimation, QEasingCurve
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        # Import WebEngine before creating QApplication (shared OpenGL contexts).
        from .panel import ControlPanel

        upstream._log = state_listener._log = lambda *args: None
        upstream.CONFIG_FILE = engine.root / "pet.private.json"
        if QApplication.instance() is None:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.singleton = QSharedMemory(instance_key)
        if not self.singleton.create(1):
            raise RuntimeError("小鲸桌宠已经运行")
        self.app.setQuitOnLastWindowClosed(False)
        upstream.apply_codex_style(self.app, [directory / "pet", directory / "pet/assets"])
        config = upstream.load_config(upstream.CONFIG_FILE)
        config.update(pet="xiaojing-chibi", fps=12, scale=engine.config["pet_size"] / 218)
        asset = load_companion(AssetPet)
        controller = self

        class ConnectedPet(upstream.PetWidget):
            def _build_pixmaps(self):
                self._pixmaps = {state: [QPixmap.fromImage(pil_to_qimage(frame)) for frame in frames]
                                 for state, frames in self._pet.frames.items()}

            def _on_circle_clicked(self):
                engine.set_enabled(False)
                voice.stop()

            def mousePressEvent(self, event):
                controller.last_interaction = time.monotonic()
                if controller.motion is not None:
                    controller.motion.stop()
                self.press_at = event.globalPosition().toPoint()
                super().mousePressEvent(event)

            def mouseReleaseEvent(self, event):
                short_click = hasattr(self, "press_at") and (event.globalPosition().toPoint() - self.press_at).manhattanLength() < 6
                super().mouseReleaseEvent(event)
                if short_click and event.button() == Qt.MouseButton.LeftButton:
                    controller.interact()

            def mouseDoubleClickEvent(self, event):
                controller.open_panel()
                event.accept()

            def enterEvent(self, event):
                if hasattr(controller, "widget") and not self._dragging and time.monotonic() > controller.hover_after:
                    controller.hover_after = time.monotonic() + 8
                    controller.play("wave", 1.8)

            def wheelEvent(self, event):
                size = max(100, min(400, engine.config["pet_size"] + (10 if event.angleDelta().y() > 0 else -10)))
                engine.configure({"pet_size": size})
                event.accept()

        self.engine, self.voice, self.url = engine, voice, url
        self.panel_type = ControlPanel
        self.panel = None
        self.pose, self.pose_until = "idle", 0.0
        self.last_interaction = time.monotonic()
        self.next_idle = time.monotonic() + random.uniform(9, 16)
        self.hover_after = 0
        self.click_times = []
        self.motion = None
        self.motion_type = QPropertyAnimation
        self.point_type = QPoint
        self.easing = QEasingCurve.Type.InOutSine
        self.last_reply = None
        self.last_state = None
        self.last_size = engine.config["pet_size"]
        self.next_stroll = time.monotonic() + random.uniform(30, 50)
        self.widget = ConnectedPet(asset, config, [asset])
        self.widget.setWindowTitle("小鲸 · Q版桌宠")
        menu = self.widget._menu
        menu.addSeparator()
        menu.addAction("打开小鲸的小窝", self.open_panel)
        menu.addAction("开启持续陪看", lambda: engine.set_enabled(True))
        menu.addAction("暂停观看", lambda: engine.set_enabled(False))
        menu.addAction("复制配对码", lambda: self.app.clipboard().setText(engine.config["token"]))
        menu.addAction("停止说话", voice.stop)
        self.tray = QSystemTrayIcon(self.widget.current_icon(), self.app)
        self.tray.setToolTip("小鲸 · 双击打开小窝")
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.open_panel() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        self.widget.show()
        self.capture_excluded = self.exclude_from_capture()
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(160)
        self.app.aboutToQuit.connect(voice.stop)
        self.play("wave", 2.0)
        self.refresh()

    def open_panel(self):
        if self.panel is None:
            self.panel = self.panel_type(self.url, self.engine.config["token"])
        self.panel.showNormal()
        self.panel.raise_()
        self.panel.activateWindow()

    def exclude_from_capture(self):
        results = [bool(ctypes.windll.user32.SetWindowDisplayAffinity(int(w.winId()), 0x11))
                   for w in (self.widget, self.widget._bubble)]
        return all(results)

    def play(self, pose, seconds=3):
        if pose not in POSES:
            return
        self.pose = pose
        self.pose_until = time.monotonic() + seconds
        self.widget.set_state(pose, "manual")
        self.engine.pet_state = dict(pose=pose, label=POSES[pose], ready=True)

    def interact(self):
        now = time.monotonic()
        self.last_interaction = now
        self.click_times = [t for t in self.click_times if now - t < 2] + [now]
        self.play("angry" if len(self.click_times) >= 3 else random.choice(("happy", "love", "cheer")), 2.5)

    def stroll(self):
        if self.widget._dragging or not self.widget.isVisible():
            return
        geo = self.widget.screen().availableGeometry()
        direction = random.choice((-1, 1))
        target_x = max(geo.left()+10, min(self.widget.x()+direction*70, geo.right()-self.widget.width()-10))
        direction = 1 if target_x > self.widget.x() else -1
        self.play("walkpass", 2.6)
        self.widget.set_state("running-right" if direction > 0 else "running-left", "manual")
        self.motion = self.motion_type(self.widget, b"pos")
        self.motion.setDuration(2400)
        self.motion.setStartValue(self.widget.pos())
        self.motion.setEndValue(self.point_type(target_x, self.widget.y()))
        self.motion.setEasingCurve(self.easing)
        self.motion.start()

    def refresh(self):
        now = time.monotonic()
        status = self.engine.status()
        config = self.engine.config
        if config["pet_size"] != self.last_size:
            self.last_size = config["pet_size"]
            self.widget._config["scale"] = self.last_size / 218
            self.widget._resize_to_pet()
            # Keep the pet within the screen after growing it.
            geo = self.widget.screen().availableGeometry()
            self.widget.move(max(geo.left(), min(self.widget.x(), geo.right()-self.widget.width())),
                             max(geo.top(), min(self.widget.y(), geo.bottom()-self.widget.height())))
        self.widget._show_bubble = config["bubbles"]
        self.widget._timer.setInterval(250 if config["reduced_motion"] else 83)
        with self.engine.lock:
            command = self.engine.pet_commands.popleft() if self.engine.pet_commands else None
        if command:
            self.last_interaction = now
            self.play(command, 4)
        elif self.voice.speaking:
            if self.pose != "talk":
                self.play("talk", 0.5)
            self.pose_until = now + 0.5
        elif now > self.pose_until and not self.widget._dragging:
            target = "think" if status["enabled"] else "idle"
            if not status["enabled"] and now - self.last_interaction > 180 and config["activity"] != "quiet":
                target = "sleep"
            if self.pose != target:
                self.play(target, 0)
            if config["activity"] != "quiet" and not config["reduced_motion"] and now > self.next_idle:
                self.play(random.choice(("eat", "basin", "sing", "happy", "think")), random.uniform(3, 5))
                spacing = (10, 20) if config["activity"] == "lively" else (24, 42)
                self.next_idle = now + random.uniform(*spacing)
            if config["activity"] == "lively" and not config["reduced_motion"] and now > self.next_stroll:
                self.stroll()
                self.next_stroll = now + random.uniform(45, 80)
        state = status["enabled"], status["error"], self.voice.speaking, self.voice.error, config["bubbles"]
        if state != self.last_state:
            self.last_state = state
            model = self.widget._model
            model.title = "小鲸"
            model.phrase = "正在说话" if self.voice.speaking else ("陪你一起看" if status["enabled"] else "在这里陪你")
            model.body = status["error"] or self.voice.error or (status["reply"]["text"] if status["reply"] else "双击打开小窝 · 轻点和我互动")
            model.visible = bool(status["error"] or status["reply"])
            self.widget._update_bubble()
        reply = status["reply"]
        if reply and reply["at"] != self.last_reply:
            self.last_reply = reply["at"]
            self.widget._model.body = reply["text"]
            self.widget._model.visible = True
            self.widget._update_bubble()
            self.play("talk", 4)
            if config.get("voice_key"):
                self.voice.say(reply["text"])

    def run(self):
        self.app.exec()
