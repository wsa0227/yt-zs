"""Offscreen UI regression checks using real services and an injectable clock."""

import os
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout, QLabel, QPushButton, QScrollArea, QSystemTrayIcon

from rehab_assistant import APP_NAME, APP_SLOGAN
from rehab_assistant.app import MainWindow
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.storage.database import migrate
from rehab_assistant.ui.theme import COLORS


class FakeClock:
    def __init__(self):
        self.value = datetime(2026, 10, 13, 8, tzinfo=timezone.utc)
        self.ticks = 0.0

    def now(self):
        return self.value

    def monotonic(self):
        return self.ticks

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)
        self.ticks += seconds


class SilentChannel:
    def notify(self, reminder):
        pass


class MainWindowDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FakeClock()
        self.posture = PostureService(self.connection, self.clock)
        self.reminders = ReminderService(self.connection, self.posture, SilentChannel(), clock=self.clock)
        self.tray = QSystemTrayIcon()
        self.window = MainWindow(self.tray, self.posture, self.reminders)
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window._refresh_timer.stop()
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.connection.close()

    def buttons(self):
        layout = self.window._action_layout
        return [layout.itemAt(i).widget() for i in range(layout.count())]

    def refresh(self):
        self.window._refresh_posture()
        self.application.processEvents()

    def test_product_name_and_slogan_are_used_in_main_window(self):
        self.assertEqual(APP_NAME, "宇安")
        self.assertEqual(APP_SLOGAN, "予慧宇，一份日常的安心")
        self.assertEqual(APP_NAME, self.window.windowTitle())
        self.assertEqual(APP_NAME, self.window._brand_title.text())
        self.assertEqual(APP_SLOGAN, self.window._sidebar_quote.text())

    def test_unknown_never_displays_an_invented_timer(self):
        self.assertEqual("--:--", self.window._elapsed.text())
        self.assertEqual("尚未确认姿势", self.window._summary.text())
        self.assertEqual(["现在坐着", "现在已起身"], [b.text() for b in self.buttons()])
        self.assertEqual("primary", self.buttons()[0].property("role"))
        self.assertIsNone(self.window._track._seconds)
        self.assertTrue(any("不必坐满" in item.text() for item in self.window._hero.findChildren(QLabel)))

    def test_manual_buttons_keep_existing_state_transitions(self):
        self.buttons()[0].click()
        self.assertEqual("SITTING", self.posture.state.posture)
        self.assertEqual("00:00", self.window._elapsed.text())
        self.clock.advance(754)
        self.refresh()
        self.assertEqual("12:34", self.window._elapsed.text())
        self.buttons()[0].click()
        self.assertEqual("UP", self.posture.state.posture)
        self.assertEqual("--:--", self.window._elapsed.text())
        self.assertEqual("重新坐下", self.buttons()[0].text())

    def test_pause_and_resume_still_require_confirmation(self):
        self.buttons()[0].click()
        self.buttons()[1].click()
        self.assertEqual("PAUSED", self.posture.state.posture)
        self.assertEqual("--:--", self.window._elapsed.text())
        self.buttons()[0].click()
        self.assertEqual("UNKNOWN", self.posture.state.posture)
        self.assertEqual("--:--", self.window._elapsed.text())
        self.assertEqual(["现在坐着", "现在已起身"], [b.text() for b in self.buttons()])

    def test_interrupted_gap_is_not_rendered_as_certain_time(self):
        self.posture.confirm_sitting()
        self.clock.advance(600)
        self.posture.observe_environment("sleep_started")
        self.refresh()
        self.assertEqual("中断后待核实", self.window._summary.text())
        self.assertEqual("--:--", self.window._elapsed.text())
        self.buttons()[0].click()
        self.assertIn("按上次确认推算，可能不准确", self.window._notice.text())
        self.assertIn("推算", self.window._timer_caption.text())
        self.assertIn("推算", self.window._elapsed.accessibleName())

    def test_cannot_confirm_button_returns_to_unknown(self):
        self.posture.confirm_sitting()
        self.posture.observe_environment("session_locked")
        self.refresh()
        self.buttons()[2].click()
        self.assertEqual("UNKNOWN", self.posture.state.posture)
        self.assertEqual("--:--", self.window._elapsed.text())

    def test_threshold_warning_remains_after_acknowledgement(self):
        self.posture.confirm_sitting()
        self.clock.advance(35 * 60)
        self.refresh()
        self.assertEqual("warning", self.window._notice.property("tone"))
        self.clock.advance(5 * 60)
        self.refresh()
        self.assertEqual("danger", self.window._notice.property("tone"))
        session_id = self.posture.state.session_id
        while self.window._reminder_layout.count():
            row = self.window._reminder_layout.itemAt(0).widget()
            row.findChild(QPushButton).click()
        self.assertEqual((), self.reminders.pending_reminders())
        self.assertEqual("SITTING", self.posture.state.posture)
        self.assertEqual(session_id, self.posture.state.session_id)
        self.assertEqual("40:00", self.window._elapsed.text())
        self.assertEqual("danger", self.window._notice.property("tone"))
        self.assertIn("上限", self.window._headline.text())

    def test_timer_refresh_preserves_buttons_and_keyboard_focus(self):
        self.buttons()[0].click()
        button = self.buttons()[0]
        button.setFocus()
        self.clock.advance(1)
        self.refresh()
        self.assertIs(button, self.buttons()[0])
        self.assertIs(button, self.window.focusWidget())
        self.assertGreaterEqual(button.height(), 44)
        self.assertTrue(button.accessibleName())

    def test_keyboard_can_confirm_and_focus_survives_state_change(self):
        self.buttons()[0].setFocus()
        QTest.keyClick(self.buttons()[0], Qt.Key.Key_Space)
        self.application.processEvents()
        self.assertEqual("SITTING", self.posture.state.posture)
        self.assertIs(self.buttons()[0], self.window.focusWidget())
        QTest.keyClick(self.buttons()[0], Qt.Key.Key_Tab)
        self.assertIs(self.buttons()[1], self.window.focusWidget())

    def test_small_window_stacks_cards_and_all_five_reminders(self):
        self.posture.confirm_sitting()
        self.clock.advance(55 * 60)
        self.window.resize(520, 540)
        self.refresh()
        self.assertEqual(QBoxLayout.Direction.TopToBottom, self.window._content_layout.direction())
        self.assertEqual(QBoxLayout.Direction.TopToBottom, self.window._action_layout.direction())
        self.assertEqual(5, self.window._reminder_layout.count())
        scroll = self.window.centralWidget()
        self.assertIsInstance(scroll, QScrollArea)
        self.assertEqual(0, scroll.horizontalScrollBar().maximum())
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        for i in range(5):
            row = self.window._reminder_layout.itemAt(i).widget()
            button = row.findChild(QPushButton)
            self.assertLessEqual(button.geometry().right(), row.width())
            scroll.ensureWidgetVisible(button)
            self.assertTrue(button.isVisible())
            self.assertGreaterEqual(button.height(), 44)
        self.window.resize(1040, 780)
        self.refresh()
        self.assertEqual(QBoxLayout.Direction.LeftToRight, self.window._content_layout.direction())
        self.assertEqual(0, scroll.horizontalScrollBar().maximum())

    def test_operation_failure_is_visible_without_mutating_state(self):
        with patch.object(self.posture, "confirm_sitting", side_effect=RuntimeError("injected")):
            with self.assertLogs("rehab_assistant.ui.main_window", level="ERROR"):
                self.window._run_posture_action(self.posture.confirm_sitting)
        self.assertTrue(self.window._error_message.isVisible())
        self.assertIn("操作未完成", self.window._error_message.text())
        self.assertEqual("UNKNOWN", self.posture.state.posture)

    def test_long_running_timer_does_not_overflow_or_wrap(self):
        self.posture.confirm_sitting()
        self.clock.advance(6000 * 60 + 12)
        self.window.resize(520, 540)
        self.refresh()
        self.assertEqual("6000:12", self.window._elapsed.text())
        self.assertFalse(self.window._elapsed.wordWrap())
        self.assertEqual(0, self.window.centralWidget().horizontalScrollBar().maximum())

    def test_reference_layout_has_accessible_pages_and_no_mock_statistics(self):
        buttons = self.window._nav_buttons
        self.assertEqual(["首页", "症状记录", "康复训练", "数据统计", "设置", "帮助"], [title for _, title in buttons])
        for index, (button, title) in enumerate(buttons):
            self.assertTrue(button.isEnabled())
            self.assertEqual(title, button.accessibleName())
            button.click()
            self.application.processEvents()
            self.assertTrue(button.isChecked())
            self.assertEqual(1, sum(item.isChecked() for item, _ in buttons))
            self.assertTrue(self.window._pages[self.window._current_page].isVisible())
        self.window.show_page("home")
        self.assertEqual("—", self.window._today_time.text())
        self.assertEqual("—", self.window._today_up.text())
        self.assertFalse(self.window._side_panel.isVisible())

    def test_ring_angle_color_and_paint_match_elapsed_time(self):
        from rehab_assistant.ui.widgets import ThresholdRing
        ring = self.window._track
        self.assertIsInstance(ring, ThresholdRing)
        def painted_color():
            image = ring.grab().toImage()
            scale = image.devicePixelRatio()
            return image.pixelColor(round((ring.width() - 17) * scale),
                                    round(ring.height() / 2 * scale)).name().upper()
        self.assertEqual(0, ring.progress_fraction)
        self.assertEqual(COLORS["track"], painted_color())
        self.posture.confirm_sitting()
        self.clock.advance(28 * 60 + 15)
        self.refresh()
        self.assertAlmostEqual(1695 / 2400, ring.progress_fraction)
        self.assertEqual("normal", ring.tone)
        self.assertEqual(COLORS["green"], painted_color())
        self.clock.advance(705)
        self.refresh()
        self.assertEqual(1, ring.progress_fraction)
        self.assertEqual("danger", ring.tone)
        self.assertEqual(COLORS["danger"], painted_color())
        self.clock.advance(60)
        self.refresh()
        self.assertEqual(1, ring.progress_fraction)
        self.assertEqual("41:00", self.window._elapsed.text())

    def test_countdown_uses_existing_35_40_and_bounded_repeat_schedule(self):
        self.posture.confirm_sitting()
        self.clock.advance(28 * 60 + 15)
        self.refresh()
        self.assertEqual("6:45", self.window._next_value.text())
        self.assertEqual("距 35 分钟还有 6:45", self.window._countdown.text())
        for seconds, expected, hint in (
            (2100, "5:00", "40 分钟"), (2400, "5:00", "有限重复提醒"),
            (2700, "5:00", "有限重复提醒"), (3000, "5:00", "有限重复提醒"),
            (3300, "已达提醒上限", "无后续定时提醒"),
        ):
            self.clock.advance(seconds - self.clock.ticks)
            self.refresh()
            self.assertEqual(expected, self.window._next_value.text())
            self.assertIn(hint, self.window._next_hint.text())
        self.assertEqual("danger", self.window._notice.property("tone"))

    def test_pause_and_gap_do_not_show_a_definite_countdown(self):
        self.posture.confirm_sitting()
        self.clock.advance(600)
        self.posture.pause()
        self.refresh()
        self.assertEqual("等待确认", self.window._next_value.text())
        self.assertEqual("追踪已暂停", self.window._next_hint.text())
        self.posture.resume_needs_confirmation()
        self.posture.confirm_sitting()
        self.posture.observe_environment("sleep_started")
        self.refresh()
        self.assertEqual("等待核实", self.window._next_value.text())
        self.assertIsNone(self.window._track._seconds)
        self.assertIn("上次坐姿确认于", self.window._started_at.text())
        self.posture.reconcile_continue_sitting()
        self.refresh()
        self.assertIn("推算", self.window._countdown.text())
        self.assertIn("推算", self.window._track.accessibleName())
        self.assertIn("推算", self.window._next_hint.text())

    def test_session_start_is_displayed_in_local_time_not_fixture_text(self):
        self.assertIn("尚无已确认", self.window._started_at.text())
        self.posture.confirm_sitting()
        self.refresh()
        start = datetime.fromisoformat(self.posture.state.sitting_since).astimezone()
        self.assertEqual(f"本次坐姿开始于 {start:%Y-%m-%d %H:%M}", self.window._started_at.text())
        self.posture.confirm_up()
        self.refresh()
        self.assertIn("尚无已确认", self.window._started_at.text())

    def test_limit_button_and_warning_do_not_reset_on_read(self):
        self.posture.confirm_sitting()
        self.clock.advance(2400)
        self.refresh()
        first = self.buttons()[0]
        self.assertEqual("danger", first.property("tone"))
        self.assertEqual("我已起身", first.text())
        for reminder in self.reminders.pending_reminders():
            self.window._acknowledge_reminder(reminder.id)
        self.assertFalse(self.window._side_panel.isVisible())
        self.assertEqual("danger", self.window._track.tone)
        self.assertEqual("danger", self.buttons()[0].property("tone"))
        self.assertEqual("40:00", self.window._elapsed.text())

    def test_os_constrained_width_shrinks_ring_without_horizontal_clipping(self):
        # Simulate an OS constraint below the requested 520 px minimum.
        self.window.setMinimumSize(320, 400)
        self.posture.confirm_sitting()
        self.clock.advance(6000 * 60 + 12)
        for width in (416, 360, 320, 520, 1040):
            self.window.resize(width, 540)
            self.refresh()
            scroll = self.window.centralWidget()
            self.assertEqual(0, scroll.horizontalScrollBar().maximum(), width)
            self.assertLessEqual(self.window._track.width(), self.window._ring_panel.width(), width)
            self.assertEqual("6000:12", self.window._elapsed.text())
            self.assertFalse(self.window.grab().isNull())
        self.assertEqual(300, self.window._track.width())

    def test_svg_assets_and_icons_render_without_missing_resources(self):
        from rehab_assistant.ui.widgets import ASSETS, brand_icon, icon
        from PySide6.QtSvg import QSvgRenderer
        for path in ASSETS.glob("*.svg"):
            self.assertTrue(QSvgRenderer(str(path)).isValid(), path)
        self.assertEqual(3, len(list(ASSETS.glob("*.svg"))))
        self.assertFalse(brand_icon().isNull())
        for name in ("home", "record", "training", "chart", "settings", "bell", "clock", "up"):
            self.assertFalse(icon(name).pixmap(32, 32).isNull(), name)
        self.assertFalse(self.window.grab().isNull())

    def test_core_text_color_pairs_have_accessible_contrast(self):
        def luminance(color):
            values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            values = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
            return sum(value * weight for value, weight in zip(values, (0.2126, 0.7152, 0.0722)))
        for foreground, background in (
            (COLORS["text"], COLORS["hero"]), (COLORS["muted"], COLORS["background"]),
            (COLORS["muted"], COLORS["hero"]), ("#FFFFFF", COLORS["primary"]),
            (COLORS["warning"], COLORS["warning_bg"]), (COLORS["danger"], COLORS["danger_bg"]),
        ):
            high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
            self.assertGreaterEqual((high + 0.05) / (low + 0.05), 4.5, (foreground, background))
