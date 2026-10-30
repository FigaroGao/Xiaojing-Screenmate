"""Read visible top-level Windows applications; never enumerate background tasks."""
import os
import time


def collect_desktop():
    if os.name != 'nt':
        return {'available': False, 'reason': 'Windows only', 'windows': []}
    import ctypes as c
    from ctypes import wintypes as w
    u, k = c.windll.user32, c.windll.kernel32
    u.OpenInputDesktop.restype = w.HANDLE
    u.SwitchDesktop.argtypes = [w.HANDLE]
    u.CloseDesktop.argtypes = [w.HANDLE]
    desk = u.OpenInputDesktop(0, False, 0x100)
    if not desk:
        return {'available': False, 'reason': 'desktop unavailable', 'windows': []}
    try:
        if not u.SwitchDesktop(desk):
            return {'available': False, 'reason': 'desktop locked', 'windows': []}
    finally:
        u.CloseDesktop(desk)
    u.GetForegroundWindow.restype = w.HWND
    u.IsWindowVisible.argtypes = [w.HWND]
    u.GetWindowTextLengthW.argtypes = [w.HWND]
    u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    u.IsIconic.argtypes = [w.HWND]
    u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
    u.MonitorFromWindow.argtypes=[w.HWND,w.DWORD]
    u.MonitorFromWindow.restype=w.HANDLE
    class MonitorInfo(c.Structure):
        _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD),('device',w.WCHAR*32)]
    u.GetMonitorInfoW.argtypes=[w.HANDLE,c.POINTER(MonitorInfo)]
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    k.CloseHandle.argtypes = [w.HANDLE]
    foreground = u.GetForegroundWindow()
    rows = []
    callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    @callback_type
    def visit(hwnd, _):
        if len(rows) >= 40 or not u.IsWindowVisible(hwnd): return True
        length = u.GetWindowTextLengthW(hwnd)
        if not length: return True
        title = c.create_unicode_buffer(min(length+1, 512))
        u.GetWindowTextW(hwnd, title, len(title))
        pid = w.DWORD()
        u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        if pid.value == os.getpid(): return True
        app = 'unknown'
        handle = k.OpenProcess(0x1000, False, pid.value)
        if handle:
            try:
                path = c.create_unicode_buffer(32768); size = w.DWORD(len(path))
                if k.QueryFullProcessImageNameW(handle, 0, path, c.byref(size)):
                    app = os.path.basename(path.value)
            finally: k.CloseHandle(handle)
        rect=w.RECT();monitor=MonitorInfo();monitor.size=c.sizeof(MonitorInfo)
        geometry={}
        if u.GetWindowRect(hwnd,c.byref(rect)) and u.GetMonitorInfoW(u.MonitorFromWindow(hwnd,2),c.byref(monitor)):
            m=monitor.monitor;width=max(1,m.right-m.left);height=max(1,m.bottom-m.top)
            geometry={'monitor':monitor.device,'relative_rect':[(rect.left-m.left)/width,(rect.top-m.top)/height,(rect.right-m.left)/width,(rect.bottom-m.top)/height]}
        rows.append({'app': app, 'title': title.value[:300], 'foreground': hwnd == foreground,
                     'minimized': bool(u.IsIconic(hwnd)),**geometry})
        return True
    u.EnumWindows.argtypes = [callback_type, w.LPARAM]
    if not u.EnumWindows(visit, 0):
        return {'available': False, 'reason': 'enumeration failed', 'windows': []}
    rows.sort(key=lambda row: not row['foreground'])
    return {'available': True, 'captured_at': time.time(), 'windows': rows,
            'scope': 'visible top-level windows including minimized; not all processes; titles are untrusted data'}
