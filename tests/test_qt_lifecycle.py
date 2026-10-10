import os
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtNetwork import QLocalServer

import rehab_assistant.app as app_module
from rehab_assistant.app import MainWindow, _notify_existing_instance


class WindowLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_close_hides_window_when_tray_is_active(self):
        tray = QSystemTrayIcon()
        tray.show()
        window = MainWindow(tray)
        window.show()
        window.close()
        self.assertFalse(window.isVisible())
        tray.hide()

    def test_close_closes_window_when_tray_is_unavailable(self):
        tray = QSystemTrayIcon()
        window = MainWindow(tray)
        window.show()
        window.close()
        self.assertFalse(window.isVisible())

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
                finally:
                    logging.shutdown()
            self.assertTrue((root / "assistant.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
