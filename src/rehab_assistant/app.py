"""Qt application composition root."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QLockFile, QStandardPaths, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from rehab_assistant import APP_ID, APP_NAME
from rehab_assistant.adapters import autostart
from rehab_assistant.adapters.windows.environment import WindowsEnvironmentMonitor
from rehab_assistant.adapters.windows.notifications import TrayNotificationChannel
from rehab_assistant.storage.database import open_database
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService


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


class MainWindow(QMainWindow):
    def __init__(
        self,
        tray: QSystemTrayIcon,
        posture: PostureService | None = None,
        reminders: ReminderService | None = None,
        environment=None,
    ) -> None:
        super().__init__()
        self._tray = tray
        self._posture = posture
        self._reminders = reminders
        self._environment = environment
        self._rendered_posture = None
        self._rendered_reminders = ()
        self._allow_exit = False
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(420, 240)
        self._summary = QLabel()
        self._elapsed = QLabel()
        self._actions = QWidget()
        self._action_layout = QHBoxLayout(self._actions)
        self._reminder_actions = QWidget()
        self._reminder_layout = QHBoxLayout(self._reminder_actions)
        layout = QVBoxLayout()
        layout.addWidget(self._summary)
        layout.addWidget(self._elapsed)
        layout.addWidget(self._actions)
        layout.addWidget(self._reminder_actions)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_posture)
        self._refresh_timer.start(1000)
        self._refresh_posture()

    def _refresh_posture(self) -> None:
        if self._posture is None:
            self._summary.setText("应用框架已启动；坐姿追踪尚未启用")
            self._elapsed.setText("")
            return
        if self._environment is not None:
            try:
                self._environment.poll_once()
            except Exception:
                logging.getLogger(__name__).exception("Environment polling failed")
        if self._reminders is not None:
            try:
                self._reminders.evaluate_and_deliver()
            except Exception:
                logging.getLogger(__name__).exception("Reminder evaluation failed")
        state = self._posture.state
        labels = {
            "UNKNOWN": "尚未确认姿势",
            "SITTING": "坐姿中" + ("（按上次确认推算，可能不准确）" if state.uncertain else ""),
            "UP": "已起身",
            "PAUSED": "暂停追踪",
            "NEEDS_CONFIRMATION": "中断后待核实",
        }
        self._summary.setText(labels[state.posture])
        state = self._posture.state
        seconds = self._posture.elapsed_seconds()
        pending = self._reminders.pending_reminders() if self._reminders is not None else ()
        pending_labels = tuple(
            f"{item.threshold_minutes}分钟" for item in pending
        )
        if seconds is not None:
            self._elapsed.setText(
                f"本次坐姿 {seconds // 60:02d}:{seconds % 60:02d} · "
                f"待处理提醒：{', '.join(pending_labels) or '无'}"
            )
        else:
            self._elapsed.setText("有未核实区间" if state.posture == "NEEDS_CONFIRMATION" else "")
        render_key = (state.posture, tuple(item.id for item in pending))
        if self._rendered_posture == state.posture and self._rendered_reminders == render_key[1]:
            return
        self._rendered_posture = state.posture
        self._rendered_reminders = render_key[1]
        while self._action_layout.count():
            item = self._action_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        actions = {
            "UNKNOWN": (("现在坐着", self._posture.confirm_sitting), ("现在已起身", self._posture.confirm_up)),
            "SITTING": (("我已起身", self._posture.confirm_up), ("暂停追踪", self._posture.pause)),
            "UP": (("重新坐下", self._posture.confirm_sitting), ("暂停追踪", self._posture.pause)),
            "PAUSED": (("恢复并重新确认", self._posture.resume_needs_confirmation),),
            "NEEDS_CONFIRMATION": (
                ("一直坐着（自述）", self._posture.reconcile_continue_sitting),
                ("现在已起身", self._posture.confirm_up),
                ("无法确认", self._posture.reconcile_unknown),
            ),
        }
        for text, callback in actions[state.posture]:
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, fn=callback: self._run_posture_action(fn))
            self._action_layout.addWidget(button)
        while self._reminder_layout.count():
            item = self._reminder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for reminder in pending:
            button = QPushButton(f"知道了 {reminder.threshold_minutes} 分钟提醒")
            button.clicked.connect(
                lambda _checked=False, delivery_id=reminder.id: self._acknowledge_reminder(delivery_id)
            )
            self._reminder_layout.addWidget(button)

    def _run_posture_action(self, callback) -> None:
        try:
            callback()
        except Exception:
            logging.getLogger(__name__).exception("Posture action failed")
        self._refresh_posture()

    def _acknowledge_reminder(self, delivery_id: int) -> None:
        if self._reminders is None:
            return
        try:
            self._reminders.acknowledge_seen(delivery_id)
        except Exception:
            logging.getLogger(__name__).exception("Reminder acknowledgement failed")
        self._refresh_posture()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_exit or not self._tray.isVisible():
            event.accept()
        else:
            event.ignore()
            self.hide()


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
    directory.mkdir(parents=True, exist_ok=True)

    lock = QLockFile(str(directory / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        _notify_existing_instance(APP_ID)
        return 0

    try:
        configure_logging(directory)
        log = logging.getLogger(__name__)
        database = open_database(directory / "assistant.sqlite3")
        posture = PostureService(database)
    except Exception:
        logging.getLogger(__name__).exception("Application initialization failed")
        if "database" in locals():
            database.close()
        lock.unlock()
        logging.shutdown()
        return 1

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(not tray_available)
    tray = QSystemTrayIcon(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon), app)
    tray.setToolTip(APP_NAME)
    menu = QMenu()
    reminders = ReminderService(database, posture, TrayNotificationChannel(tray))
    environment = WindowsEnvironmentMonitor()
    window = MainWindow(tray, posture, reminders, environment)
    environment._window = window
    environment.start(
        lambda event_type, payload: posture.observe_environment(event_type, payload)
    )

    show_action = QAction("打开主窗口", menu)
    show_action.triggered.connect(window.showNormal)
    menu.addAction(show_action)

    startup_action = QAction("登录时启动", menu)
    startup_action.setCheckable(True)
    startup_action.setChecked(autostart.is_enabled())

    def toggle_startup(enabled: bool) -> None:
        try:
            autostart.set_enabled(enabled)
        except (OSError, ImportError):
            log.exception("Could not update login startup setting")
            startup_action.setChecked(autostart.is_enabled())

    startup_action.toggled.connect(toggle_startup)
    menu.addAction(startup_action)

    exit_action = QAction("退出", menu)

    def exit_application() -> None:
        window._allow_exit = True
        tray.hide()
        app.quit()

    exit_action.triggered.connect(exit_application)
    menu.addAction(exit_action)
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
        environment.close()
        posture.close()
        database.close()
        lock.unlock()
        logging.shutdown()
    return result
