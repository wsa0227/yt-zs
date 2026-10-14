import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSystemTrayIcon

from rehab_assistant.domain.exercises import ExerciseRecord
from rehab_assistant.services.exercise_service import ExerciseService
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.storage.database import migrate
from rehab_assistant.ui.main_window import MainWindow


class FakeClock:
    def now(self):
        from datetime import datetime, timezone
        return datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)

    def monotonic(self):
        return 0.0


class SilentChannel:
    def notify(self, title, message):
        return None


class ExercisePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FakeClock()
        posture = PostureService(self.connection, self.clock)
        reminders = ReminderService(self.connection, posture, SilentChannel(), clock=self.clock)
        self.service = ExerciseService(self.connection, self.clock)
        self.window = MainWindow(QSystemTrayIcon(), posture, reminders, None, None, self.service)
        self.window.show()
        self.window._refresh_timer.stop()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.connection.close()

    def test_empty_catalog_has_real_add_entry_and_empty_plan(self):
        page = self.window._pages["training"]
        self.assertTrue(next(button for button in page.findChildren(QPushButton)
                             if button.text() == "添加资料候选").isEnabled())
        content = "\n".join(item.text() for item in page.findChildren(QLabel))
        self.assertIn("尚无已录入的训练资料候选", content)
        self.assertIn("尚无可执行训练计划", content)
        self.assertNotIn("猫牛式", content)

    def test_approved_plan_is_rendered_and_suspension_is_visible(self):
        record = self.service.save_candidate(ExerciseRecord(
            id=None,
            name="医生提供的动作资料",
            source_url="",
            source_org="专业人员提供",
            content="按专业人员提供的说明执行。",
            contraindication_notes="出现不适立即停止。",
            reviewer=None,
            approved_at_utc=None,
            status="CANDIDATE",
            created_at_utc=None,
            updated_at_utc=None,
        ))
        self.service.approve(record.id, "康复治疗师")
        self.service.add_to_plan(record.id)
        page = self.window._pages["training"]
        page.refresh_training()
        self.application.processEvents()
        content = "\n".join(item.text() for item in page.findChildren(QLabel))
        self.assertIn("医生提供的动作资料", content)
        self.assertIn("执行计划中", content)
        self.assertIn("记录本次训练", "\n".join(item.text() for item in page.findChildren(QPushButton)))

        self.service.suspend(record.id, "暂时停用")
        page.refresh_training()
        self.application.processEvents()
        content = "\n".join(item.text() for item in page.findChildren(QLabel))
        self.assertIn("已停用 · 不可执行", content)
        self.assertIn("不会再产生训练提醒", content)

    def test_training_page_with_real_service_fits_narrow_window(self):
        record = self.service.save_candidate(ExerciseRecord(
            id=None,
            name="专业资料候选",
            source_url="",
            source_org="专业人员提供",
            content="按专业人员提供的说明执行。",
            contraindication_notes="出现不适立即停止。",
            reviewer=None,
            approved_at_utc=None,
            status="CANDIDATE",
            created_at_utc=None,
            updated_at_utc=None,
        ))
        self.service.approve(record.id, "康复治疗师")
        self.service.add_to_plan(record.id)
        self.window.resize(520, 740)
        self.window.show_page("training")
        self.application.processEvents()
        self.assertEqual(0, self.window.centralWidget().horizontalScrollBar().maximum())


if __name__ == "__main__":
    unittest.main()
