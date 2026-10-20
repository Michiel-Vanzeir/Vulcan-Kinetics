"""Resolve the focused app and text field on Windows via UI Automation.

The app comes from the foreground window's process and title, because Electron/WebView2
apps like new Teams host their text fields in helper processes, and browsers need the
title to tell work apps from personal pages. The field identity and password flag come
from the focused UI Automation element. UIA's IsPassword covers Win32 ES_PASSWORD edits
as well as password inputs in web content.
"""

import ctypes
import os
from ctypes import wintypes

import uiautomation as auto

from agent.surfaces import Surface, is_sensitive_field, surface_name

# uiautomation writes its own log to @AutomationLog.txt by default; the agent writes nothing to disk.
auto.Logger.SetLogFile("")

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_CF_UNICODETEXT = 13
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_user32.GetClipboardData.restype = wintypes.HANDLE
_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]


def clipboard_text_length() -> int:
    """Length of the text on the clipboard, for paste counts. The text itself is never kept."""
    if not _user32.OpenClipboard(None):
        return 0
    try:
        handle = _user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return 0
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            return 0
        try:
            return len(ctypes.wstring_at(pointer))
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


def _process_name(hwnd: int) -> str | None:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return None
        return os.path.basename(path.value).lower()
    finally:
        _kernel32.CloseHandle(handle)


def _window_title(hwnd: int) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, title, length + 1)
    return title.value


def focused_surface() -> Surface | None:
    """Return the focused field, or None if it can't be resolved or isn't a work surface.

    Must be called from a thread wrapped in auto.UIAutomationInitializerInThread.
    """
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    process = _process_name(hwnd)
    name = surface_name(process, _window_title(hwnd)) if process else None
    if name is None:
        return None
    control = auto.GetFocusedControl()
    if control is None:
        return None
    runtime_id = ".".join(str(part) for part in control.GetRuntimeId())
    is_sensitive = bool(control.Element.CurrentIsPassword) or is_sensitive_field(
        control.Name or "", control.AutomationId or ""
    )
    return Surface(id=f"{name}:{runtime_id}", name=name, is_sensitive=is_sensitive)
