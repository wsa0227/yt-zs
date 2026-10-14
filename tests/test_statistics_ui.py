"""Qt checks for the real statistics page and home summaries."""

import os
import sqlite3
import unittest
from datetime import datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.services.statistics_service import StatisticsService
from rehab_assistant.storage.database import migrate
from rehab_assistant.ui.main_window import MainWindow


class FixedClock:
    def __init__(self):
        self.value = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.ticks = 0.0

    def now(self):
        return self.value

    def monotonic(self):
        return self.ticks


class SilentChannel:
    def notify(self, reminder):
        del reminder


class StatisticsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FixedClock()
        self.posture = PostureService(self.connection, self.clock)
        self.reminders = ReminderService(self.connection, self.posture, SilentChannel(), clock=self.clock)
        self.statistics = StatisticsService(
            self.connection, clock=self.clock, local_timezone=timezone.utc
        )
        self.window = MainWindow(
            QSystemTrayIcon(), self.posture, self.reminders,
            statistics_service=self.statistics,
        )
        self.window._refresh_timer.stop()
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.connection.close()

    def test_real_statistics_page_uses_service_and_switches_7_30_days(self):
        self.posture.confirm_sitting()
        self.clock.value = datetime(2026, 10, 14, 12, 15, tzinfo=timezone.utc)
        self.posture.confirm_up()
        self.window._refresh_statistics()

        page = self.window._pages["chart"]
        self.window.show_page("chart")
        self.application.processEvents()
        self.assertNotIn("趋势图占位", page.status.text())
        self.assertEqual(7, len(page._statistics_charts["sitting"]._rows))
        self.assertEqual("15 分", self.window._today_time.text())
        self.assertEqual("1 次", self.window._today_up.text())

        page._statistics_period.setCurrentIndex(1)
        self.application.processEvents()
        self.assertEqual(30, len(page._statistics_charts["sitting"]._rows))

    def test_missing_values_are_not_drawn_as_zero_and_refresh_is_read_only(self):
        page = self.window._pages["chart"]
        page._statistics_period.setCurrentIndex(0)
        self.application.processEvents()
        before = self.connection.total_changes
        page.refresh_history()
        self.application.processEvents()
        self.assertEqual(before, self.connection.total_changes)
        self.assertTrue(all(page._statistics_charts[mode]._value(row) is None
                            for mode in page._statistics_charts
                            for row in page._statistics_charts[mode]._rows))
        self.assertEqual("—", self.window._today_time.text())
        self.assertEqual("—", self.window._today_up.text())

    def test_empty_service_data_is_explicitly_empty(self):
        page = self.window._pages["chart"]
        self.assertIn("本机已保存记录", page.status.text())
        self.assertIn("未知区间单独展示", page.feedback.text())
        self.assertTrue(all("暂无记录" in chart.toolTip() for chart in page._statistics_charts.values()))


if __name__ == "__main__":
    unittest.main()
