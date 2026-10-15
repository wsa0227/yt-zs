import os
import logging
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QLockFile, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtNetwork import QLocalServer

import rehab_assistant.app as app_module
from rehab_assistant.app import MainWindow, _notify_existing_instance


class WindowLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_default_instance_server_name_stays_compatible(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app_module.APP_ID, app_module.instance_server_name(Path("unused")))

    def test_smoke_data_directories_have_isolated_stable_ipc_names(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {"REHAB_ASSISTANT_DATA_DIR": str(root)}):
                first = app_module.instance_server_name(root)
                self.assertNotEqual(app_module.APP_ID, first)
                self.assertEqual(first, app_module.instance_server_name(root / "child" / ".."))
                self.assertNotEqual(first, app_module.instance_server_name(root / "second"))

    def test_close_hides_window_when_tray_is_active(self):
        tray = QSystemTrayIcon()
        tray.show()
        window = MainWindow(tray)
        window.show()
        window.close()
        self.assertFalse(window.isVisible())
        self.assertTrue(window._refresh_timer.isActive())
        window._refresh_timer.stop()
        window.deleteLater()
        tray.hide()

    def test_close_closes_window_when_tray_is_unavailable(self):
        tray = QSystemTrayIcon()
        window = MainWindow(tray)
        window.show()
        window.close()
        self.assertFalse(window.isVisible())
        self.assertFalse(window._refresh_timer.isActive())
        window.deleteLater()

    def test_second_instance_sends_activation_message(self):
        server = QLocalServer()
        name = f"rehab-assistant-test-{uuid4().hex}"
        self.assertTrue(server.listen(name))
        loop = QEventLoop()
        received = []

        def accept_connection():
            connection = server.nextPendingConnection()
            if connection is None:
                return

            def read_message():
                received.append(bytes(connection.readAll()))
                connection.write(b"ok")
                connection.flush()
                loop.quit()

            connection.readyRead.connect(read_message)
            if connection.bytesAvailable():
                read_message()

        server.newConnection.connect(accept_connection)
        try:
            QTimer.singleShot(0, lambda: self.assertTrue(_notify_existing_instance(name)))
            QTimer.singleShot(1000, loop.quit)
            loop.exec()
            self.assertEqual([b"activate"], received)
        finally:
            server.close()
            QLocalServer.removeServer(name)

    def test_held_lock_without_activation_server_reports_startup_failure(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            holder = QLockFile(str(root / "app.lock"))
            self.assertTrue(holder.tryLock(0))
            error = StringIO()
            try:
                with (
                    patch.object(app_module, "data_directory", return_value=root),
                    patch.object(app_module, "APP_ID", f"missing-server-{uuid4().hex}"),
                    patch.object(app_module, "configure_logging") as configure,
                    redirect_stderr(error),
                ):
                    result = app_module.main()
                self.assertNotEqual(0, result)
                self.assertIn("app.lock", error.getvalue())
                configure.assert_not_called()
                self.assertFalse((root / "assistant.sqlite3").exists())
                self.assertTrue((root / "app.lock").exists())
            finally:
                holder.unlock()

    def test_held_lock_with_activation_acknowledgement_returns_success(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            holder = QLockFile(str(root / "app.lock"))
            self.assertTrue(holder.tryLock(0))
            try:
                with (
                    patch.object(app_module, "data_directory", return_value=root),
                    patch.object(app_module, "_notify_existing_instance", return_value=True) as notify,
                    patch.object(app_module, "configure_logging") as configure,
                ):
                    self.assertEqual(0, app_module.main())
                notify.assert_called_once_with(app_module.APP_ID)
                configure.assert_not_called()
                self.assertFalse((root / "assistant.sqlite3").exists())
            finally:
                holder.unlock()

    def test_lock_permission_error_is_not_treated_as_an_existing_instance(self):
        with TemporaryDirectory() as directory:
            with (
                patch.object(app_module, "data_directory", return_value=Path(directory)),
                patch.object(app_module, "QLockFile") as lock_type,
                patch.object(app_module, "_notify_existing_instance") as notify,
                redirect_stderr(StringIO()) as error,
            ):
                lock_type.LockError = QLockFile.LockError
                lock_type.return_value.tryLock.return_value = False
                lock_type.return_value.error.return_value = QLockFile.LockError.PermissionError
                self.assertEqual(1, app_module.main())
            notify.assert_not_called()
            self.assertIn("PermissionError", error.getvalue())

    def test_invalid_data_directory_reports_error(self):
        with TemporaryDirectory() as directory:
            file = Path(directory) / "not-a-directory"
            file.write_text("occupied", encoding="utf-8")
            with (
                patch.object(app_module, "data_directory", return_value=file),
                redirect_stderr(StringIO()) as error,
            ):
                self.assertEqual(1, app_module.main())
            self.assertIn(str(file), error.getvalue())

    def test_initialization_error_reports_reason_and_releases_lock(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(app_module, "data_directory", return_value=root),
                patch.object(app_module, "configure_logging", side_effect=OSError("log unavailable")),
                patch.object(app_module, "open_database") as database,
                patch.object(app_module.logging.getLogger(app_module.__name__), "exception"),
                redirect_stderr(StringIO()) as error,
            ):
                self.assertEqual(1, app_module.main())
            database.assert_not_called()
            self.assertIn("log unavailable", error.getvalue())
            self.assertFalse((root / "app.lock").exists())

    def test_application_bootstraps_database_and_exits(self):
        original_exec = self.application.exec

        def auto_quit(application):
            QTimer.singleShot(0, application.quit)
            return original_exec()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(app_module, "data_directory", return_value=root),
                patch.object(app_module.autostart, "is_enabled", return_value=False),
                patch.object(
                    QApplication,
                    "exec",
                    auto_quit,
                ),
            ):
                try:
                    self.assertEqual(0, app_module.main())
                    windows = [w for w in self.application.topLevelWidgets() if isinstance(w, MainWindow)]
                    for window in windows:
                        self.assertFalse(window._refresh_timer.isActive())
                        window.deleteLater()
                finally:
                    logging.shutdown()
            self.assertTrue((root / "assistant.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
