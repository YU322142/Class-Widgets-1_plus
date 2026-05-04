from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import psutil


@dataclass
class ForegroundWindowSnapshot:
    title: str = ""
    class_name: str = ""
    process_name: str = ""
    status: int = 0
    pid: int = 0


def get_foreground_window_snapshot() -> ForegroundWindowSnapshot:
    if sys.platform == "win32":
        return _get_windows_snapshot()
    if sys.platform == "darwin":
        return _get_macos_snapshot()
    return _get_linux_snapshot()


# ============================================================
# Windows
# ============================================================

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wintypes

    _user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    MONITOR_DEFAULTTONEAREST = 2

    def _foreground_hwnd():
        try:
            return _user32.GetForegroundWindow()
        except Exception:
            return 0

    def _window_text(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(hwnd, buf, len(buf))
        return buf.value or ""

    def _window_class_name(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, len(buf))
        return buf.value or ""

    def _window_pid(hwnd: int) -> int:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)

    def _window_process_name(pid: int) -> str:
        if not pid:
            return ""
        try:
            return psutil.Process(pid).name()
        except Exception:
            return ""

    def _window_status(hwnd: int) -> int:
        """
        0 - 正常
        1 - 最大化
        2 - 最小化
        3 - 全屏
        """
        if not hwnd:
            return 0

        try:
            if _user32.IsIconic(hwnd):
                return 2
        except Exception:
            pass

        try:
            monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if monitor and _user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                wr = RECT()
                if _user32.GetWindowRect(hwnd, ctypes.byref(wr)):
                    if (
                        wr.left <= mi.rcMonitor.left
                        and wr.top <= mi.rcMonitor.top
                        and wr.right >= mi.rcMonitor.right
                        and wr.bottom >= mi.rcMonitor.bottom
                    ):
                        return 3
        except Exception:
            pass

        try:
            if _user32.IsZoomed(hwnd):
                return 1
        except Exception:
            pass

        return 0

    def _get_windows_snapshot() -> ForegroundWindowSnapshot:
        hwnd = _foreground_hwnd()
        if not hwnd:
            return ForegroundWindowSnapshot()

        pid = _window_pid(hwnd)
        return ForegroundWindowSnapshot(
            title=_window_text(hwnd),
            class_name=_window_class_name(hwnd),
            process_name=_window_process_name(pid),
            status=_window_status(hwnd),
            pid=pid,
        )

else:
    def _get_windows_snapshot() -> ForegroundWindowSnapshot:
        return ForegroundWindowSnapshot()


# ============================================================
# macOS
# ============================================================

def _approx_equal(a: float, b: float, tol: float = 6.0) -> bool:
    return abs(a - b) <= tol


def _rect_like_equal(bounds: dict[str, float], target: dict[str, float], tol: float = 6.0) -> bool:
    return (
        _approx_equal(bounds.get("x", 0), target.get("x", 0), tol)
        and _approx_equal(bounds.get("y", 0), target.get("y", 0), tol)
        and _approx_equal(bounds.get("w", 0), target.get("w", 0), tol)
        and _approx_equal(bounds.get("h", 0), target.get("h", 0), tol)
    )


def _get_macos_snapshot() -> ForegroundWindowSnapshot:
    if sys.platform != "darwin":
        return ForegroundWindowSnapshot()

    try:
        from AppKit import NSWorkspace, NSScreen
        import Quartz
    except Exception:
        return ForegroundWindowSnapshot()

    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return ForegroundWindowSnapshot()

        pid = int(app.processIdentifier())
        app_name = str(app.localizedName() or "")
        bundle_id = str(app.bundleIdentifier() or "")
        process_name = app_name or bundle_id

        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )

        chosen: dict[str, Any] | None = None
        for w in windows:
            try:
                owner_pid = int(w.get("kCGWindowOwnerPID", 0))
            except Exception:
                owner_pid = 0
            if owner_pid != pid:
                continue

            layer = int(w.get("kCGWindowLayer", 9999))
            if chosen is None:
                chosen = w
            if layer == 0:
                chosen = w
                break

        title = ""
        status = 0

        if chosen is not None:
            title = str(chosen.get("kCGWindowName", "") or "")
            bounds_dict = chosen.get("kCGWindowBounds", {}) or {}
            bounds = {
                "x": float(bounds_dict.get("X", 0.0)),
                "y": float(bounds_dict.get("Y", 0.0)),
                "w": float(bounds_dict.get("Width", 0.0)),
                "h": float(bounds_dict.get("Height", 0.0)),
            }

            main_screen = NSScreen.mainScreen()
            if main_screen is not None:
                frame = main_screen.frame()
                visible = main_screen.visibleFrame()

                full_rect = {
                    "x": float(frame.origin.x),
                    "y": float(frame.origin.y),
                    "w": float(frame.size.width),
                    "h": float(frame.size.height),
                }
                visible_rect = {
                    "x": float(visible.origin.x),
                    "y": float(visible.origin.y),
                    "w": float(visible.size.width),
                    "h": float(visible.size.height),
                }

                if _rect_like_equal(bounds, full_rect, 8.0):
                    status = 3
                elif _rect_like_equal(bounds, visible_rect, 8.0):
                    status = 1
                else:
                    status = 0

        class_name = bundle_id or process_name

        return ForegroundWindowSnapshot(
            title=title,
            class_name=class_name,
            process_name=process_name,
            status=status,
            pid=pid,
        )
    except Exception:
        return ForegroundWindowSnapshot()


# ============================================================
# Linux (X11)
# ============================================================

def _run_cmd(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _parse_wm_class(text: str) -> str:
    # 例：WM_CLASS(STRING) = "code", "Code"
    m = re.findall(r'"([^"]+)"', text)
    if not m:
        return ""
    return m[-1]


def _parse_pid(text: str) -> int:
    m = re.search(r"=\s*(\d+)", text)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0


def _linux_tools_available() -> bool:
    return shutil.which("xdotool") is not None and shutil.which("xprop") is not None


def _get_linux_snapshot() -> ForegroundWindowSnapshot:
    if sys.platform in ("win32", "darwin"):
        return ForegroundWindowSnapshot()

    # Wayland 下一般拿不到可靠前台窗口信息
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return ForegroundWindowSnapshot()

    if not _linux_tools_available():
        return ForegroundWindowSnapshot()

    win_id = _run_cmd(["xdotool", "getactivewindow"])
    if not win_id:
        return ForegroundWindowSnapshot()

    title = _run_cmd(["xdotool", "getwindowname", win_id])

    wm_class_text = _run_cmd(["xprop", "-id", win_id, "WM_CLASS"])
    class_name = _parse_wm_class(wm_class_text)

    pid_text = _run_cmd(["xprop", "-id", win_id, "_NET_WM_PID"])
    pid = _parse_pid(pid_text)

    process_name = ""
    if pid:
        try:
            process_name = psutil.Process(pid).name()
        except Exception:
            process_name = ""

    state_text = _run_cmd(["xprop", "-id", win_id, "_NET_WM_STATE"])
    wm_state_text = _run_cmd(["xprop", "-id", win_id, "WM_STATE"])

    status = 0
    state_upper = state_text.upper()
    wm_state_upper = wm_state_text.upper()

    if "_NET_WM_STATE_FULLSCREEN" in state_upper:
        status = 3
    elif "_NET_WM_STATE_HIDDEN" in state_upper or "ICONIC" in wm_state_upper:
        status = 2
    elif "_NET_WM_STATE_MAXIMIZED_VERT" in state_upper and "_NET_WM_STATE_MAXIMIZED_HORZ" in state_upper:
        status = 1
    else:
        status = 0

    return ForegroundWindowSnapshot(
        title=title,
        class_name=class_name,
        process_name=process_name,
        status=status,
        pid=pid,
    )
