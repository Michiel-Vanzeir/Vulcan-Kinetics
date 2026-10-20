"""Open the whoknows people panel (people-panel.html) as a small popup window.

Uses Edge or Chrome in app mode: no tabs or address bar. The page gets the field's topic
tokens in its URL, never typed text. It runs on a separate browser profile, so it doesn't
touch the user's own browser windows.

Placement is done by us, not by the browser: once the window exists it is moved to the top
right of the work area on the monitor the user was typing on, sized for that monitor's
scaling. Browser flags for position are unreliable with display scaling and several screens.

Try it without the agent: python -m agent.panel notice_period country_BE
"""

import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from ctypes import wintypes
from pathlib import Path

from topic_extractor import is_vocab_token

log = logging.getLogger(__name__)

PANEL_FILE = Path(__file__).resolve().parents[2] / "people-panel.html"
PANEL_TITLE = "whoknows people panel"  # the <title> of people-panel.html
PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "whoknows" / "panel-profile"
WIDTH, HEIGHT = 500, 860  # at 100% scaling; Chrome windows are at least ~500 wide
MARGIN = 16
FIND_TIMEOUT_S = 8.0
SETTLE_S = 3.0

_user32 = ctypes.windll.user32
_shcore = ctypes.windll.shcore
_MONITOR_DEFAULTTONEAREST = 2
_MDT_EFFECTIVE_DPI = 0
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
_SWP_NOZORDER = 0x0004
_SWP_SHOWWINDOW = 0x0040
_SW_RESTORE = 9
_WM_CLOSE = 0x0010
CLOSE_TIMEOUT_S = 2.0

_BROWSERS = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def find_browser() -> str | None:
    """Path to Edge or Chrome, or None."""
    for candidate in _BROWSERS:
        path = Path(os.path.expandvars(candidate))
        if path.is_file():
            return str(path)
    return shutil.which("msedge") or shutil.which("chrome")


def panel_url(topics: list[str]) -> str:
    """file:// URL of the panel in popup mode. Only vocabulary topic tokens go in the URL."""
    tokens = [t for t in topics if is_vocab_token(t)]
    query = urllib.parse.urlencode({"popup": "1", "topics": ",".join(tokens)})
    return f"{PANEL_FILE.as_uri()}?{query}"


def _find_panel_windows() -> list[int]:
    """Handles of all visible top-level panel windows."""
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def check(hwnd, _lparam):
        length = _user32.GetWindowTextLengthW(hwnd)
        if length and _user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, title, length + 1)
            if PANEL_TITLE in title.value:
                found.append(hwnd)
        return True

    _user32.EnumWindows(check, 0)
    return found


def _top_right_rect(anchor_hwnd: int | None) -> tuple[int, int, int, int]:
    """(x, y, width, height) in physical pixels on the monitor of `anchor_hwnd`.

    Must run with per-monitor DPI awareness, so coordinates are real pixels.
    """
    monitor = _user32.MonitorFromWindow(anchor_hwnd, _MONITOR_DEFAULTTONEAREST)
    info = _MonitorInfo(cbSize=ctypes.sizeof(_MonitorInfo))
    _user32.GetMonitorInfoW(monitor, ctypes.byref(info))
    dpi_x, dpi_y = wintypes.UINT(96), wintypes.UINT(96)
    _shcore.GetDpiForMonitor(monitor, _MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
    scale = dpi_x.value / 96
    work = info.rcWork
    margin = round(MARGIN * scale)
    width = min(round(WIDTH * scale), work.right - work.left - 2 * margin)
    height = min(round(HEIGHT * scale), work.bottom - work.top - 2 * margin)
    return work.right - width - margin, work.top + margin, width, height


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def _place_when_ready(anchor_hwnd: int | None) -> None:
    """Wait for the panel window, move it on screen, and keep it there while it settles."""
    # Per-thread, so the rest of the agent keeps its default DPI behaviour.
    _user32.SetThreadDpiAwarenessContext(_PER_MONITOR_AWARE_V2)
    deadline = time.monotonic() + FIND_TIMEOUT_S
    while not _find_panel_windows():
        if time.monotonic() > deadline:
            log.warning("panel window did not appear within %.0f s", FIND_TIMEOUT_S)
            return
        time.sleep(0.05)
    target = _top_right_rect(anchor_hwnd)
    focused: set[int] = set()
    # Chrome may re-apply a saved placement, or swap in a new window, shortly after
    # showing it. Keep every panel window on target until things settle.
    settle_until = time.monotonic() + SETTLE_S
    while time.monotonic() < settle_until:
        for hwnd in _find_panel_windows():
            if _window_rect(hwnd) != target:
                _user32.ShowWindow(hwnd, _SW_RESTORE)
                _user32.SetWindowPos(hwnd, None, *target, _SWP_NOZORDER | _SWP_SHOWWINDOW)
            if hwnd not in focused:
                _user32.SetForegroundWindow(hwnd)
                focused.add(hwnd)
        time.sleep(0.05)


def _forget_saved_placement() -> None:
    """Drop Chrome's remembered window position for the panel, so it can't reopen off screen."""
    preferences = PROFILE_DIR / "Default" / "Preferences"
    try:
        data = json.loads(preferences.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.pop("app_window_placement", None) is not None:
        preferences.write_text(json.dumps(data), encoding="utf-8")


class PanelWindow:
    """One popup at a time: opening again replaces the previous window."""

    def __init__(self, browser: str | None = None):
        self._browser = browser or find_browser()
        self._placer: threading.Thread | None = None
        # The hotkey (capture thread) and doubt alerts (transport thread) can both open it.
        self._lock = threading.Lock()

    def open(self, topics: list[str]) -> None:
        """Show the panel, pre-filtered on these topic tokens, on the user's current monitor."""
        with self._lock:
            self._open(topics)

    def open_unless_shown(self, topics: list[str]) -> None:
        """Open the panel for a doubt alert, but never replace one the user already has open."""
        with self._lock:
            if not _find_panel_windows():
                self._open(topics)

    def _open(self, topics: list[str]) -> None:
        url = panel_url(topics)
        anchor = _user32.GetForegroundWindow() or None
        self.close()
        _forget_saved_placement()
        if self._browser is None:
            # Fallback: a normal browser tab. Works, just not as a popup.
            webbrowser.open(url)
            return
        subprocess.Popen(
            [
                self._browser,
                f"--app={url}",
                f"--window-size={WIDTH},{HEIGHT}",
                f"--user-data-dir={PROFILE_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._placer = threading.Thread(target=_place_when_ready, args=(anchor,), daemon=True)
        self._placer.start()
        log.info("panel opened with %d topics", len(topics))

    def wait_until_placed(self) -> None:
        """Block until the window has been placed (or placement gave up)."""
        if self._placer is not None:
            self._placer.join()

    def close(self) -> None:
        """Close every open panel window and wait until they are gone.

        Closing the window (rather than killing the process) lets Chrome exit cleanly; the
        process we start only hands the window to the running browser."""
        for hwnd in _find_panel_windows():
            _user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        deadline = time.monotonic() + CLOSE_TIMEOUT_S
        while _find_panel_windows() and time.monotonic() < deadline:
            time.sleep(0.05)


if __name__ == "__main__":
    window = PanelWindow()
    window.open(sys.argv[1:])
    window.wait_until_placed()
