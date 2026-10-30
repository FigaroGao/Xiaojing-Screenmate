"""Native transparency and screen-coordinate helpers for the desktop overlay."""
import ctypes
import sys


class WindowIntegration:
    def __init__(self, widget):
        self.widget = widget
        self.transparent = None
        self.excluded = False
        if sys.platform == "win32":
            self.user = ctypes.windll.user32
            self.user.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            self.user.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            self.user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            self.user.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            self.user.SetWindowDisplayAffinity.restype = ctypes.c_bool

    def exclude(self):
        if sys.platform == "win32":
            self.excluded = bool(self.user.SetWindowDisplayAffinity(int(self.widget.winId()), 0x11))
        return self.excluded

    def passthrough(self, enabled):
        if self.transparent == enabled:
            return
        if sys.platform == "win32":
            hwnd = int(self.widget.winId())
            old = self.user.GetWindowLongPtrW(hwnd, -20)
            flags = old | 0x20 if enabled else old & ~0x20
            self.user.SetWindowLongPtrW(hwnd, -20, flags)
        self.transparent = enabled
