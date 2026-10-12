import sqlite3
import unittest
from ctypes import addressof, wintypes

from rehab_assistant.adapters.windows.environment import (
    ManualEnvironmentMonitor,
    WindowsEnvironmentMonitor,
    _NativeEventFilter,
)
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.storage.database import migrate

from PySide6.QtWidgets import QApplication, QWidget


class EnvironmentAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_manual_monitor_has_start_emit_close_lifecycle(self):
        monitor = ManualEnvironmentMonitor()
        events = []
        monitor.start(lambda event_type, payload: events.append((event_type, payload)))
        monitor.emit("idle_started", {"idle_seconds": 60})
        monitor.close()
        monitor.emit("idle_ended")
        self.assertEqual([("idle_started", {"idle_seconds": 60})], events)

    def test_idle_is_an_environment_fact_and_does_not_change_posture(self):
        connection = sqlite3.connect(":memory:")
        migrate(connection)
        posture = PostureService(connection)
        posture.confirm_sitting()
        monitor = ManualEnvironmentMonitor()
        monitor.start(posture.observe_environment)

        monitor.emit("idle_started", {"idle_seconds": 600})
        monitor.emit("idle_ended", {"idle_seconds": 0})

        self.assertEqual("SITTING", posture.state.posture)
        self.assertEqual(2, connection.execute(
            "SELECT COUNT(*) FROM environment_events"
        ).fetchone()[0])
        self.assertEqual(0, connection.execute(
            "SELECT COUNT(*) FROM posture_events WHERE event_type='interrupted'"
        ).fetchone()[0])
        connection.close()

    def test_lock_and_sleep_enter_confirmation_without_unlocking_automatically(self):
        connection = sqlite3.connect(":memory:")
        migrate(connection)
        posture = PostureService(connection)
        posture.confirm_sitting()
        monitor = ManualEnvironmentMonitor()
        monitor.start(posture.observe_environment)

        monitor.emit("session_locked")
        self.assertEqual("NEEDS_CONFIRMATION", posture.state.posture)
        monitor.emit("session_unlocked")
        monitor.emit("resume")
        self.assertEqual("NEEDS_CONFIRMATION", posture.state.posture)
        connection.close()

    def test_environment_database_failure_does_not_mutate_posture(self):
        connection = sqlite3.connect(":memory:")
        migrate(connection)
        posture = PostureService(connection)
        posture.confirm_sitting()
        connection.execute("DROP TABLE environment_events")
        before = posture.state

        with self.assertRaises(sqlite3.OperationalError):
            posture.observe_environment("session_locked")

        self.assertEqual(before, posture.state)
        connection.close()

    def test_windows_monitor_native_messages_are_safe_facts(self):
        monitor = WindowsEnvironmentMonitor()
        events = []
        monitor.start(lambda event_type, payload: events.append((event_type, payload)))
        monitor.handle_native_message((monitor.WM_WTSSESSION_CHANGE, monitor.WTS_SESSION_LOCK, 3))
        monitor.handle_native_message((monitor.WM_POWERBROADCAST, monitor.PBT_APMSUSPEND, 0))
        monitor.handle_native_message((monitor.WM_POWERBROADCAST, monitor.PBT_APMRESUMEAUTOMATIC, 0))
        monitor.close()
        self.assertEqual(
            ["session_locked", "sleep_started", "resume"],
            [event[0] for event in events],
        )

    def test_windows_monitor_decodes_qt_msg_pointer(self):
        monitor = WindowsEnvironmentMonitor()
        events = []
        monitor.start(lambda event_type, payload: events.append((event_type, payload)))
        message = wintypes.MSG()
        message.message = monitor.WM_WTSSESSION_CHANGE
        message.wParam = monitor.WTS_SESSION_LOCK
        message.lParam = 9

        self.assertTrue(monitor.handle_native_message(addressof(message)))
        self.assertEqual("session_locked", events[0][0])
        self.assertEqual(9, events[0][1]["session_id"])
        monitor.close()

    def test_native_event_filter_returns_qt_result_tuple(self):
        monitor = WindowsEnvironmentMonitor()
        monitor.start(lambda *_event: None)
        event_filter = _NativeEventFilter(monitor)
        message = wintypes.MSG()
        message.message = monitor.WM_POWERBROADCAST
        message.wParam = monitor.PBT_APMSUSPEND

        self.assertEqual(
            (True, 0),
            event_filter.nativeEventFilter(b"windows_generic_MSG", addressof(message)),
        )
        self.assertEqual(
            (False, 0),
            event_filter.nativeEventFilter(b"other", addressof(message)),
        )
        monitor.close()

    def test_windows_monitor_starts_with_a_qt_window(self):
        window = QWidget()
        window.show()
        monitor = WindowsEnvironmentMonitor(window)
        try:
            monitor.start(lambda *_event: None)
        finally:
            monitor.close()
            window.close()


if __name__ == "__main__":
    unittest.main()
