"""Qt application composition root."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QLockFile, QStandardPaths, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon,
)

from rehab_assistant import APP_ID, APP_NAME
from rehab_assistant.adapters import autostart
from rehab_assistant.adapters.windows.environment import WindowsEnvironmentMonitor
from rehab_assistant.adapters.windows.notifications import TrayNotificationChannel
from rehab_assistant.storage.database import open_database
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.services.symptom_service import SymptomService
from rehab_assistant.services.exercise_service import ExerciseService
from rehab_assistant.services.statistics_service import StatisticsService
from rehab_assistant.ui.main_window import MainWindow
from rehab_assistant.ui.widgets import brand_icon
from rehab_assistant.ui.tray_menu import build_tray_menu


def data_directory() -> Path:
    return Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    ))


def configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=directory / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        encoding="utf-8",
    )


def _notify_existing_instance(server_name: str) -> bool:
    loop = QEventLoop()
    socket = QLocalSocket()
    acknowledged = False
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)

    def send_activation() -> None:
        if socket.write(b"activate") < 0:
            loop.quit()
        else:
            socket.flush()

    def read_acknowledgement() -> None:
        nonlocal acknowledged
        acknowledged = bytes(socket.readAll()) == b"ok"
        loop.quit()

    socket.connected.connect(send_activation)
    socket.readyRead.connect(read_acknowledgement)
    socket.errorOccurred.connect(loop.quit)
    socket.connectToServer(server_name)
    timeout.start(500)
    loop.exec()
    socket.disconnectFromServer()
    return acknowledged


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Local")
    app.setQuitOnLastWindowClosed(False)

    directory = data_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"无法创建应用数据目录：{directory}；{error}", file=sys.stderr)
        return 1

    lock = QLockFile(str(directory / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        if lock.error() == QLockFile.LockError.LockFailedError:
            if _notify_existing_instance(APP_ID):
                return 0
            pid, hostname, process_name = lock.getLockInfo()
            print(
                f"无法启动：单实例锁被占用，且无法激活已有窗口。"
                f"锁文件：{directory / 'app.lock'}；"
                f"进程：{process_name} (PID {pid})；主机：{hostname}。"
                "请先从托盘退出已有实例，或核对任务管理器中的对应进程后重试。",
                file=sys.stderr,
            )
        else:
            print(
                f"无法启动：不能获取单实例锁 {directory / 'app.lock'}；"
                f"错误：{lock.error().name}。请检查数据目录的写入权限。",
                file=sys.stderr,
            )
        return 1

    try:
        configure_logging(directory)
        log = logging.getLogger(__name__)
        database = open_database(directory / "assistant.sqlite3")
        posture = PostureService(database)
        symptoms = SymptomService(database)
        exercises = ExerciseService(database)
        statistics = StatisticsService(database)
    except Exception as error:
        print(f"应用初始化失败：{error}；数据目录：{directory}", file=sys.stderr)
        logging.getLogger(__name__).exception("Application initialization failed")
        if "database" in locals():
            database.close()
        lock.unlock()
        logging.shutdown()
        return 1

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(not tray_available)
    tray = QSystemTrayIcon(brand_icon(), app)
    tray.setToolTip(APP_NAME)
    reminders = ReminderService(database, posture, TrayNotificationChannel(tray))
    environment = WindowsEnvironmentMonitor()
    window = MainWindow(tray, posture, reminders, environment, symptoms, exercises, statistics)
    environment._window = window
    environment.start(
        lambda event_type, payload: posture.observe_environment(event_type, payload)
    )

    def exit_application() -> None:
        window._allow_exit = True
        tray.hide()
        app.quit()

    menu, _tray_actions = build_tray_menu(window, autostart, exit_application)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.showNormal()
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )

    server = QLocalServer(app)
    QLocalServer.removeServer(APP_ID)
    if not server.listen(APP_ID):
        log.error("Could not listen for single-instance activation: %s", server.errorString())
    else:
        def activate_existing() -> None:
            connection = server.nextPendingConnection()
            if connection is None:
                return

            def activate_window() -> None:
                connection.readAll()
                window.showNormal()
                connection.write(b"ok")
                connection.flush()

            if connection.bytesAvailable():
                activate_window()
            else:
                connection.readyRead.connect(activate_window)
            connection.disconnected.connect(connection.deleteLater)

        server.newConnection.connect(activate_existing)

    if tray_available:
        tray.show()
    else:
        log.warning("System tray is unavailable; window remains usable")
    window.show()

    try:
        result = app.exec()
    finally:
        window._refresh_timer.stop()
        tray.hide()
        server.close()
        environment.close()
        posture.close()
        database.close()
        lock.unlock()
        logging.shutdown()
    return result
