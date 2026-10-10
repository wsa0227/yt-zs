"""Windows environment facts, isolated from posture domain decisions."""

from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes
from typing import Callable, Protocol

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from PySide6.QtWidgets import QApplication


EnvironmentCallback = Callable[[str, dict], None]
log = logging.getLogger(__name__)


class EnvironmentMonitor(Protocol):
    def start(self, callback: EnvironmentCallback) -> None:
        ...

    def close(self) -> None:
        ...


class ManualEnvironmentMonitor:
    """Deterministic adapter used by tests and manual-mode fallback."""

    def __init__(self) -> None:
        self._callback: EnvironmentCallback | None = None
        self._closed = False

    def start(self, callback: EnvironmentCallback) -> None:
        self._callback = callback
        self._closed = False

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        if self._closed or self._callback is None:
            return
        self._callback(event_type, dict(payload or {}))

    def close(self) -> None:
        self._closed = True
        self._callback = None


class _NativeEventFilter(QAbstractNativeEventFilter):
    def __init__(self, monitor: "WindowsEnvironmentMonitor") -> None:
        super().__init__()
        self._monitor = monitor

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt API name
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG", "windows_generic_MSG", "windows_dispatcher_MSG"):
            self._monitor.handle_native_message(message)
        return False


class WindowsEnvironmentMonitor:
    """Publishes OS facts only; it never emits posture commands.

    Idle polling is explicit so the application event loop remains the owner of
    lifecycle and tests can call ``poll_once`` deterministically. Lock and
    power messages arrive through Qt's native event filter when available.
    """

    WM_WTSSESSION_CHANGE = 0x02B1
    WM_POWERBROADCAST = 0x0218
    WTS_SESSION_LOCK = 0x0007
    WTS_SESSION_UNLOCK = 0x0008
    PBT_APMSUSPEND = 0x0004
    PBT_APMRESUMEAUTOMATIC = 0x0012
    PBT_APMRESUMESUSPEND = 0x0007

    def __init__(self, window=None, *, idle_threshold_seconds: int = 60) -> None:
        self._window = window
        self._idle_threshold_seconds = max(1, idle_threshold_seconds)
        self._callback: EnvironmentCallback | None = None
        self._filter: _NativeEventFilter | None = None
        self._running = False
        self._idle = False
        self._wts_registered = False

    @property
    def available(self) -> bool:
        return os.name == "nt"

    def start(self, callback: EnvironmentCallback) -> None:
        self._callback = callback
        self._running = True
        application = QCoreApplication.instance()
        if application is not None:
            self._filter = _NativeEventFilter(self)
            application.installNativeEventFilter(self._filter)
        if not self.available:
            log.info("Windows environment APIs are unavailable; manual mode remains active")
            return
        self._register_session_notifications()

    def close(self) -> None:
        if self._filter is not None:
            application = QCoreApplication.instance()
            if application is not None:
                application.removeNativeEventFilter(self._filter)
            self._filter = None
        if self._wts_registered and self._window is not None:
            try:
                ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(
                    wintypes.HWND(int(self._window.winId()))
                )
            except (AttributeError, OSError):
                log.exception("Could not unregister Windows session notifications")
        self._wts_registered = False
        self._running = False
        self._callback = None

    def poll_once(self) -> None:
        if not self._running or not self.available:
            return
        try:
            idle_seconds = self._get_idle_seconds()
        except (AttributeError, OSError):
            log.exception("GetLastInputInfo is unavailable; idle monitoring disabled")
            return
        idle_now = idle_seconds >= self._idle_threshold_seconds
        if idle_now == self._idle:
            return
        self._idle = idle_now
        self._emit(
            "idle_started" if idle_now else "idle_ended",
            {"idle_seconds": idle_seconds},
        )

    def handle_native_message(self, message) -> bool:
        """Handle a Qt MSG pointer or a test message object."""
        if not self._running:
            return False
        try:
            message_id = int(message.message)
            wparam = int(message.wParam)
            lparam = int(message.lParam)
        except AttributeError:
            message_id, wparam, lparam = map(int, message)
        if message_id == self.WM_WTSSESSION_CHANGE:
            if wparam == self.WTS_SESSION_LOCK:
                self._emit("session_locked", {"session_id": lparam})
                return True
            if wparam == self.WTS_SESSION_UNLOCK:
                self._emit("session_unlocked", {"session_id": lparam})
                return True
        if message_id == self.WM_POWERBROADCAST:
            if wparam == self.PBT_APMSUSPEND:
                self._emit("sleep_started", {})
                return True
            if wparam in (self.PBT_APMRESUMEAUTOMATIC, self.PBT_APMRESUMESUSPEND):
                self._emit("resume", {})
                return True
        return False

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._callback is not None:
            self._callback(event_type, payload)

    @staticmethod
    def _get_idle_seconds() -> int:
        class LastInputInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LastInputInfo(ctypes.sizeof(LastInputInfo))
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            raise ctypes.WinError()
        tick_count = ctypes.windll.kernel32.GetTickCount64()
        return max(0, int((tick_count - info.dwTime) / 1000))

    def _register_session_notifications(self) -> None:
        if self._window is None:
            log.info("No Qt window was supplied; session notifications are not registered")
            return
        try:
            result = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
                wintypes.HWND(int(self._window.winId())), 0
            )
        except (AttributeError, OSError):
            log.exception("Could not register Windows session notifications")
            return
        self._wts_registered = bool(result)
        if not self._wts_registered:
            log.error("WTSRegisterSessionNotification returned failure")
