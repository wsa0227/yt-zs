import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.services.symptom_service import SymptomService
from rehab_assistant.storage.database import migrate
from rehab_assistant.ui.main_window import MainWindow
from test_ui import FakeClock, SilentChannel


class SymptomPageServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FakeClock()
        self.posture = PostureService(self.connection, self.clock)
        self.reminders = ReminderService(
            self.connection, self.posture, SilentChannel(), clock=self.clock
        )
        self.symptoms = SymptomService(self.connection, clock=self.clock)
        self.window = MainWindow(
            QSystemTrayIcon(), self.posture, self.reminders, symptom_service=self.symptoms
        )
        self.window._refresh_timer.stop()
        self.window.show()
        self.window.show_page("record")
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.connection.close()

    @property
    def page(self):
        return self.window._pages["record"]

    def save(self):
        self.page.save_button.click()
        self.application.processEvents()

    def test_save_renders_history_and_fixed_safety_feedback(self):
        page = self.page
        page.score.setValue(4)
        page.body_checks[0].setChecked(True)
        page.safety_checks["perineal_numbness"].setChecked(True)
        page.notes.setPlainText("今天久坐后不适")

        self.save()

        self.assertEqual(1, self.symptoms.count())
        self.assertEqual(1, page.history_table.rowCount())
        self.assertIn("已保存", page.feedback.text())
        self.assertIn("会阴或肛周麻木", page.feedback.text())
        saved = self.symptoms.get_by_date(date.today().isoformat())
        self.assertEqual(4, saved.pain_score)
        self.assertEqual(("下腰部",), saved.body_locations)

    def test_same_day_edit_loads_existing_record_and_updates_one_row(self):
        page = self.page
        page.score.setValue(2)
        self.save()
        self.assertEqual(1, page.history_table.rowCount())

        page.history_table.selectRow(0)
        page.edit_button.click()
        self.application.processEvents()
        self.assertEqual(2, page.score.value())
        self.assertIn("已载入", page.feedback.text())

        page.score.setValue(7)
        self.save()

        self.assertEqual(1, self.symptoms.count())
        self.assertEqual(1, page.history_table.rowCount())
        self.assertEqual(7, self.symptoms.get_by_date(date.today().isoformat()).pain_score)

    def test_delete_requires_confirmation_and_removes_selected_record(self):
        self.page.score.setValue(3)
        self.save()
        self.page.history_table.selectRow(0)

        with patch(
            "rehab_assistant.ui.pages.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            self.page.delete_button.click()
        self.assertEqual(1, self.symptoms.count())

        with patch(
            "rehab_assistant.ui.pages.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.page.delete_button.click()
        self.application.processEvents()
        self.assertEqual(0, self.symptoms.count())
        self.assertEqual(0, self.page.history_table.rowCount())

    def test_save_failure_does_not_show_success_or_mutate_storage(self):
        self.page.score.setValue(5)
        with patch.object(self.symptoms, "save", side_effect=RuntimeError("injected")):
            with self.assertLogs("rehab_assistant.ui.pages", level="ERROR"):
                self.save()

        self.assertEqual(0, self.symptoms.count())
        self.assertIn("保存失败", self.page.feedback.text())
        self.assertNotIn("已保存", self.page.feedback.text())

    def test_export_confirms_destination_and_writes_csv(self):
        self.page.score.setValue(6)
        self.save()
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "symptoms.csv")
            with patch(
                "rehab_assistant.ui.pages.QFileDialog.getSaveFileName",
                return_value=(path, "CSV 文件 (*.csv)"),
            ), patch(
                "rehab_assistant.ui.pages.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                self.page.export_button.click()
            self.application.processEvents()
            self.assertTrue(os.path.exists(path))
            self.assertIn("已导出 1 条", self.page.feedback.text())


if __name__ == "__main__":
    unittest.main()
