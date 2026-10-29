"""Thin adapter around LINNoot/dsh-co-pet's existing PetWidget.

Rendering, animations, assets, menus and bubbles belong to the upstream project.
See docs/THIRD_PARTY.md. This module only connects Screenmate state and actions.
"""
import ctypes
import subprocess
import sys
import webbrowser
from pathlib import Path

UPSTREAM_REVISION = "b394cdacca07526a36a36373cb11bec603b74651"


class Pet:
    def __init__(self, engine, voice, url, instance_key="xiaojing-screenmate-pet"):
        directory = Path(__file__).resolve().parents[1] / "runtime" / "dsh-co-pet"
        if not (directory / "pet" / "pet_app.py").exists():
            raise RuntimeError("请先运行 python tools/setup_pet.py 安装现有桌宠依赖")
        actual = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()
        if actual != UPSTREAM_REVISION:
            raise RuntimeError("桌宠依赖版本不同，请先检查，避免未经验证的接口变化")
        sys.path.insert(0, str(directory / "pet"))
        import pet_app as upstream
        import state_listener
        from PySide6.QtCore import QSharedMemory, QTimer
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon

        # The upstream logs snippets of bubble text; disable those logs for private chats.
        upstream._log = state_listener._log = lambda *args: None
        upstream.CONFIG_FILE = engine.root / "pet.private.json"
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.singleton = QSharedMemory(instance_key)
        if not self.singleton.create(1):
            raise RuntimeError("小鲸桌宠已经运行")
        self.app.setQuitOnLastWindowClosed(False)
        upstream.apply_codex_style(self.app, [directory / "pet", directory / "pet" / "assets"])
        config = upstream.load_config(upstream.CONFIG_FILE)
        if not config.get("pet"):
            config["pet"] = "deepseek"
        pets = upstream.scan_pets([directory / "pet"])
        pet = upstream.pick_pet(pets, config["pet"])
        if pet is None:
            raise RuntimeError("上游桌宠包不存在")

        class ConnectedPet(upstream.PetWidget):
            def _on_circle_clicked(self):
                engine.set_enabled(False)
                voice.stop()

        self.widget = ConnectedPet(pet, config, pets)
        self.widget.setWindowTitle("小鲸 · Screenmate")
        menu = self.widget._menu
        menu.addSeparator()
        menu.addAction("小鲸 · 开启持续陪看", lambda: engine.set_enabled(True))
        menu.addAction("小鲸 · 暂停观看", lambda: engine.set_enabled(False))
        menu.addAction("小鲸 · 设置与连接", lambda: webbrowser.open(url))
        menu.addAction("小鲸 · 复制配对码", lambda: self.app.clipboard().setText(engine.config["token"]))
        menu.addAction("小鲸 · 停止说话", voice.stop)
        self.tray = QSystemTrayIcon(self.widget.current_icon(), self.app)
        self.tray.setToolTip("小鲸 · Screenmate")
        self.tray.setContextMenu(menu)
        self.widget.pet_changed.connect(lambda: self.tray.setIcon(self.widget.current_icon()))
        self.tray.activated.connect(lambda reason: self.widget.set_visible(not self.widget.isVisible()))
        self.tray.show()
        self.widget.show()
        self.capture_excluded = self.exclude_from_capture()
        self.engine, self.voice = engine, voice
        self.last_reply = None
        self.last_state = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)
        self.app.aboutToQuit.connect(voice.stop)
        self.refresh()

    def exclude_from_capture(self):
        results = []
        for widget in (self.widget, self.widget._bubble):
            results.append(bool(ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), 0x11)))
        return all(results)

    def refresh(self):
        status = self.engine.status()
        state = status["enabled"], status["error"], self.voice.speaking, self.voice.error
        if state != self.last_state:
            self.last_state = state
            model = self.widget._model
            model.title = "小鲸"
            model.phrase = "说话中" if self.voice.speaking else ("陪看中" if status["enabled"] else "观看已暂停")
            model.body = status["error"] or self.voice.error or (status["reply"]["text"] if status["reply"] else "右键调整观看频率与连接")
            model.visible = True
            self.widget.set_state("running" if self.voice.speaking else "idle", "manual")
            self.widget._update_bubble()
        reply = status["reply"]
        if reply and reply["at"] != self.last_reply:
            self.last_reply = reply["at"]
            self.widget._model.body = reply["text"]
            self.widget._model.visible = True
            self.widget._update_bubble()
            if self.engine.config.get("voice_key"):
                self.voice.say(reply["text"])

    def run(self):
        self.app.exec()
