"""Smoke-test the frozen Windows executable using isolated application data.

A PyInstaller one-file executable starts a bootloader parent and an application
child. The window belongs to the child, so checking only Popen.pid is incorrect.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from tempfile import TemporaryDirectory


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)
)
kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextW.argtypes = (wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL


def _process_parents() -> dict[int, int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    parents: dict[int, int] = {}
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return parents


def _descendants(parent: int, parents: dict[int, int]) -> set[int]:
    result = {parent}
    while True:
        expanded = result | {pid for pid, ppid in parents.items() if ppid in result}
        if expanded == result:
            return result
        result = expanded


def _windows_for_pids(pids: set[int]) -> list[int]:
    windows: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, len(title))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and title.value == "宇安":
            windows.append(int(hwnd))
        return True

    user32.EnumWindows(callback, 0)
    return windows


def _is_target_process(pid: int, executable: Path) -> bool:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        name = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(name))
        return bool(kernel32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size))) and (
            os.path.normcase(os.path.abspath(name.value))
            == os.path.normcase(os.path.abspath(executable))
        )
    finally:
        kernel32.CloseHandle(handle)


def _stop_owned_process(pid: int, executable: Path) -> bool:
    # Do not terminate unrelated processes, even if a PID has been recycled.
    if not _is_target_process(pid, executable):
        return True
    handle = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        if not kernel32.TerminateProcess(handle, 1):
            return False
        return kernel32.WaitForSingleObject(handle, 5000) == WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)


def main() -> int:
    if sys.platform != "win32":
        print("RESULT=NOT_RUN platform is not Windows")
        return 2

    root = Path(__file__).resolve().parents[1]
    executable = root / "dist" / "LumbarRehabAssistant.exe"
    if not executable.is_file():
        print(f"RESULT=NOT_RUN missing executable: {executable}")
        return 2

    with TemporaryDirectory(prefix="yu-an-frozen-smoke-") as data_dir:
        environment = os.environ.copy()
        environment["REHAB_ASSISTANT_DATA_DIR"] = data_dir
        environment["QT_QPA_PLATFORM"] = "windows"
        process = subprocess.Popen([str(executable)], env=environment)
        owned_pids = {process.pid}
        result = 1
        report = "RESULT=FAIL no visible 宇安 main window"
        try:
            deadline = time.monotonic() + 35  # one-file extraction may be slow
            windows: list[int] = []
            while time.monotonic() < deadline:
                owned_pids.update(_descendants(process.pid, _process_parents()))
                verified = {pid for pid in owned_pids if _is_target_process(pid, executable)}
                windows = _windows_for_pids(verified)
                if windows:
                    break
                if process.poll() is not None and not verified:
                    report = f"RESULT=FAIL early_exit={process.returncode}"
                    break
                time.sleep(0.2)

            if windows:
                database = Path(data_dir) / "assistant.sqlite3"
                if database.is_file():
                    report = (
                        f"RESULT=PASS bootloader_pid={process.pid} "
                        f"owned_pids={sorted(owned_pids)} main_windows={len(windows)} "
                        "database_created=True cleanup=forced_test_process_only"
                    )
                    result = 0
                else:
                    report = "RESULT=FAIL visible main window without isolated database"
            elif process.poll() is None:
                report = f"RESULT=FAIL no visible main window; owned_pids={sorted(owned_pids)}"
        finally:
            # Closing the window minimizes to tray by design. For an isolated
            # smoke instance, explicitly stop the app child before its bootloader.
            cleanup_ok = True
            for pid in sorted(owned_pids - {process.pid}, reverse=True):
                cleanup_ok &= _stop_owned_process(pid, executable)
            if process.poll() is None:
                cleanup_ok &= _stop_owned_process(process.pid, executable)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cleanup_ok = False
            if not cleanup_ok:
                report = f"RESULT=FAIL cleanup incomplete; owned_pids={sorted(owned_pids)}"
                result = 1
        print(report)
        return result


if __name__ == "__main__":
    raise SystemExit(main())
