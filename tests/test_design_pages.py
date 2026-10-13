"""Design-board coverage and honest placeholder contracts, isolated from user data."""
import os
import sqlite3
import unittest
from datetime import date
from unittest.mock import Mock, patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QSystemTrayIcon, QMessageBox
from rehab_assistant.ui.main_window import MainWindow
from rehab_assistant.ui.pages import CAPABILITIES, preview_dialog
from rehab_assistant.ui.tray_menu import build_tray_menu
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.storage.database import migrate
from test_ui import FakeClock, SilentChannel


class DesignBoardCoverageTests(unittest.TestCase):
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
        self.window._refresh_timer.stop()
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        for dialog in self.window.findChildren(QDialog):
            dialog.close()
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.connection.close()

    def test_five_capabilities_match_board_and_route_to_pages(self):
        self.assertEqual(["本地运行", "开机常驻", "定时提醒", "记录趋势", "康复训练"], [entry[1] for entry in CAPABILITIES])
        self.assertEqual(5, len(self.window._features.buttons))
        for button, (_, title, subtitle, target) in zip(self.window._features.buttons, CAPABILITIES):
            self.assertIn(title, button.text())
            self.assertIn(subtitle, button.text())
            self.assertGreaterEqual(button.height(), 44)
            self.assertFalse(button.icon().isNull())
            button.click()
            self.assertEqual(target, self.window._current_page)
            self.window.show_page("home")

    def test_page_switching_does_not_change_posture_or_write_records(self):
        before = self.connection.total_changes
        for key in self.window._pages:
            self.window.show_page(key)
            self.application.processEvents()
        self.assertEqual(before, self.connection.total_changes)
        self.assertEqual("UNKNOWN", self.posture.state.posture)
        self.assertIsNone(self.posture.elapsed_seconds())

    def test_timer_and_warning_continue_on_other_pages(self):
        self.posture.confirm_sitting()
        self.window.show_page("training")
        self.clock.advance(2400)
        self.window._refresh_posture()
        self.assertEqual("training", self.window._current_page)
        self.assertEqual(2400, self.posture.elapsed_seconds())
        self.assertEqual(2, len(self.reminders.pending_reminders()))
        self.window.show_page("home")
        self.assertEqual("danger", self.window._notice.property("tone"))

    def test_symptom_form_defaults_to_missing_not_zero_and_does_not_save(self):
        page = self.window._pages["record"]
        self.assertIn("未填写", page.score_label.text())
        self.assertEqual("", page.notes.toPlainText())
        self.assertEqual(date.today().isoformat(), page.record_date.date().toString("yyyy-MM-dd"))
        page.score.setValue(3)
        self.assertIn("3 / 10（未保存）", page.score_label.text())
        buttons = page.findChildren(QPushButton)
        next(button for button in buttons if button.text() == "跳过评分").click()
        self.assertIn("未填写", page.score_label.text())
        next(button for button in buttons if button.text() == "选择 0 分").click()
        self.assertIn("0 / 10（未保存）", page.score_label.text())
        self.assertTrue(all(not b.isEnabled() for b in buttons if "待实现" in b.text()))

    def test_training_placeholders_cannot_become_executable_plan(self):
        page = self.window._pages["training"]
        self.assertEqual(["康复动作", "我的计划"], [page.tab_widget.tabText(i) for i in range(2)])
        content = "\n".join(item.text() for item in page.findChildren(QLabel))
        for text in ("猫牛式", "桥式", "腰部拉伸", "设计占位", "初始可执行训练为空", "程序无法验证"):
            self.assertIn(text, content)
        self.assertTrue(all(not b.isEnabled() for b in page.findChildren(QPushButton)))

    def test_statistics_has_three_tabs_and_no_fabricated_values(self):
        page = self.window._pages["chart"]
        self.assertEqual(["坐姿时长", "症状变化", "起身次数"], [page.tab_widget.tabText(i) for i in range(3)])
        metrics = [item.text() for item in page.findChildren(QLabel) if item.property("role") == "metric"]
        self.assertEqual(["—"] * 6, metrics)
        self.assertIn("统计与趋势", page.status.text())

    def test_all_pages_fit_os_constrained_widths_without_horizontal_scroll(self):
        # Visit all tab panels first: a previously wide hidden row must not
        # leave a cached minimum width that later clips another page.
        for key in ("training", "chart"):
            self.window.show_page(key)
            for index in range(self.window._pages[key].tab_widget.count()):
                self.window._pages[key].tab_widget.setCurrentIndex(index)
                self.application.processEvents()
        self.window.setMinimumSize(0, 0)
        for width in (1040, 700, 520, 416, 360, 320, 1040):
            self.window.resize(width, 740)
            for key in self.window._pages:
                self.window.show_page(key)
                self.application.processEvents()
                scroll = self.window.centralWidget()
                self.assertEqual(0, scroll.horizontalScrollBar().maximum(), (width, key, scroll.widget().minimumSizeHint()))
                self.assertFalse(self.window.grab().isNull())

    def test_first_narrow_render_with_all_pending_reminders_has_no_clipping(self):
        self.posture.confirm_sitting()
        self.clock.advance(3300)
        window = MainWindow(self.tray, self.posture, self.reminders)
        window._refresh_timer.stop()
        try:
            window.setMinimumSize(0, 0)
            window.resize(416, 563)
            window.show()
            self.application.processEvents()
            self.assertEqual(5, len(self.reminders.pending_reminders()))
            self.assertEqual(0, window.centralWidget().horizontalScrollBar().maximum())
        finally:
            window.close()
            window.deleteLater()
            self.application.processEvents()

    def test_tiny_window_has_a_return_navigation_when_sidebar_hidden(self):
        self.window.setMinimumSize(0, 0)
        self.window.resize(320, 740)
        self.window.show_page("record")
        self.application.processEvents()
        self.assertFalse(self.window._sidebar.isVisible())
        self.assertTrue(self.window._compact_navigation.isVisible())
        self.window._compact_navigation.setCurrentIndex(0)
        self.assertEqual("home", self.window._current_page)

    def test_navigation_is_keyboard_operable(self):
        button = self.window._nav_buttons[1][0]
        button.setFocus()
        QTest.keyClick(button, Qt.Key.Key_Space)
        self.assertEqual("record", self.window._current_page)

    def test_previews_are_explicitly_non_operational(self):
        self.posture.confirm_sitting()
        before = self.connection.total_changes
        for kind in ("startup", "warning", "limit"):
            dialog = preview_dialog(self.window, kind)
            self.application.processEvents()
            self.assertTrue(dialog.isVisible())
            self.assertIn("预览", dialog.windowTitle())
            for button in dialog.findChildren(QPushButton):
                if button.text() != "关闭预览":
                    self.assertFalse(button.isEnabled())
            self.assertEqual(before, self.connection.total_changes)
            self.assertEqual("SITTING", self.posture.state.posture)
            self.assertEqual(0, self.posture.elapsed_seconds())
            dialog.close()

    def test_dialog_previews_fit_a_constrained_window(self):
        self.window.setMinimumSize(0, 0)
        self.window.resize(320, 740)
        self.application.processEvents()
        for kind in ("startup", "warning", "limit"):
            dialog = preview_dialog(self.window, kind)
            self.application.processEvents()
            self.assertLessEqual(dialog.minimumSizeHint().width(), 320, kind)
            self.assertLessEqual(dialog.width(), 320, kind)
            dialog.close()

    def menu(self):
        provider = Mock()
        provider.enabled = False
        provider.is_enabled.side_effect = lambda: provider.enabled
        provider.set_enabled.side_effect = lambda enabled: setattr(provider, "enabled", enabled)
        exit_callback = Mock()
        menu, actions = build_tray_menu(self.window, provider, exit_callback)
        return menu, actions, provider, exit_callback

    def test_tray_has_all_board_routes_and_manual_posture_actions(self):
        menu, actions, _, _ = self.menu()
        self.assertEqual({"status", "up", "sitting", "pause", "show", "settings", "help", "startup", "exit"}, set(actions))
        self.assertFalse(actions["status"].isEnabled())
        actions["sitting"].trigger()
        self.assertEqual("SITTING", self.posture.state.posture)
        menu.aboutToShow.emit()
        self.assertFalse(actions["sitting"].isEnabled())
        actions["up"].trigger()
        self.assertEqual("UP", self.posture.state.posture)
        actions["settings"].trigger()
        self.assertEqual("settings", self.window._current_page)
        actions["help"].trigger()
        self.assertEqual("info", self.window._current_page)

    def test_tray_resume_requires_manual_confirmation(self):
        menu, actions, _, _ = self.menu()
        actions["sitting"].trigger()
        actions["pause"].trigger()
        self.assertEqual("PAUSED", self.posture.state.posture)
        menu.aboutToShow.emit()
        self.assertEqual("恢复并重新确认", actions["pause"].text())
        actions["pause"].trigger()
        self.assertEqual("UNKNOWN", self.posture.state.posture)

    def test_tray_uncertain_gap_does_not_offer_silent_restart(self):
        menu, actions, _, _ = self.menu()
        self.posture.confirm_sitting()
        self.posture.observe_environment("sleep_started")
        menu.aboutToShow.emit()
        self.assertIn("待核实", actions["status"].text())
        self.assertFalse(actions["sitting"].isEnabled())
        self.assertTrue(actions["up"].isEnabled())

    def test_startup_page_and_tray_share_existing_adapter(self):
        menu, actions, provider, _ = self.menu()
        check = self.window._pages["settings"].startup_check
        self.assertTrue(check.isEnabled())
        check.setChecked(True)
        provider.set_enabled.assert_called_once_with(True)
        self.assertTrue(actions["startup"].isChecked())
        actions["startup"].trigger()
        self.assertFalse(check.isChecked())
        self.assertEqual(2, provider.set_enabled.call_count)

    def test_failed_startup_write_restores_actual_state_without_success_message(self):
        _, actions, provider, _ = self.menu()
        provider.set_enabled.side_effect = OSError("denied")
        with self.assertLogs("rehab_assistant.ui.tray_menu", level="ERROR"):
            self.window._pages["settings"].startup_check.setChecked(True)
        self.assertFalse(actions["startup"].isChecked())
        self.assertFalse(self.window._pages["settings"].startup_check.isChecked())
        self.assertIn("未保存", self.window._pages["settings"].startup_status.text())

    def test_failed_startup_read_disables_both_controls(self):
        menu, actions, provider, _ = self.menu()
        provider.is_enabled.side_effect = OSError("denied")
        with self.assertLogs("rehab_assistant.ui.tray_menu", level="ERROR"):
            menu.aboutToShow.emit()
        self.assertFalse(actions["startup"].isEnabled())
        self.assertFalse(self.window._pages["settings"].startup_check.isEnabled())
        self.assertIn("无法读取", self.window._pages["settings"].startup_status.text())

    def test_exit_explains_loss_of_reminders_and_requires_confirmation(self):
        _, actions, _, callback = self.menu()
        with patch("rehab_assistant.ui.tray_menu.QMessageBox.question", return_value=QMessageBox.StandardButton.No) as question:
            actions["exit"].trigger()
            self.assertIn("停止计时和所有提醒", question.call_args.args[2])
            callback.assert_not_called()
        with patch("rehab_assistant.ui.tray_menu.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            actions["exit"].trigger()
        callback.assert_called_once()
