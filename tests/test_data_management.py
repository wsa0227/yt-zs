import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from rehab_assistant.domain.exercises import ExerciseRecord
from rehab_assistant.domain.symptoms import SymptomRecord
from rehab_assistant.services.data_management_service import DataManagementService
from rehab_assistant.services.exercise_service import ExerciseService
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.symptom_service import SymptomService
from rehab_assistant.storage.database import migrate, open_database


class DataManagementTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.posture = PostureService(self.connection)
        self.service = DataManagementService(self.connection, self.posture)

    def tearDown(self):
        self.connection.close()

    def _seed_health_data(self):
        self.posture.confirm_sitting()
        self.connection.execute(
            "INSERT INTO environment_events(event_id,event_type,occurred_at_utc,payload_json) "
            "VALUES('environment-1','locked','2026-10-14T08:00:00+00:00','{}')"
        )
        self.connection.execute(
            "INSERT INTO reminder_deliveries(session_id,threshold_minutes,sequence_no,"
            "scheduled_at_utc,status) VALUES(?,?,?,?,?)",
            (self.posture.state.session_id, 35, 0, "2026-10-14T08:00:00+00:00", "pending"),
        )
        SymptomService(self.connection).save(SymptomRecord(
            id=None,
            record_date_local="2026-10-14",
            pain_score=4,
            body_locations=("下腰部",),
            leg_symptoms="无新增症状",
            activity_relation="坐姿时",
            safety_flags=(),
            notes="测试记录",
            created_at_utc=None,
            updated_at_utc=None,
        ))
        exercise = ExerciseService(self.connection).save_candidate(ExerciseRecord(
            id=None,
            name="测试动作",
            source_url="https://example.invalid/test",
            source_org="测试资料",
            content="仅用于数据管理测试",
            contraindication_notes="先咨询专业人员",
            reviewer=None,
            approved_at_utc=None,
            status="CANDIDATE",
            created_at_utc=None,
            updated_at_utc=None,
        ))
        self.connection.commit()
        self.connection.execute(
            "INSERT INTO exercise_plans(exercise_id,status,added_at_utc) VALUES(?,?,?)",
            (exercise.id, "ACTIVE", "2026-10-14T08:00:00+00:00"),
        )
        self.connection.execute(
            "INSERT INTO exercise_logs(exercise_id,performed_at_utc,completed,"
            "user_response,symptom_change,notes) VALUES(?,?,?,?,?,?)",
            (exercise.id, "2026-10-14T08:30:00+00:00", 1, "无不适", "未填写", ""),
        )
        self.connection.commit()

    def _counts(self):
        return {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "symptom_entries", "exercise_logs", "exercise_plans", "exercises",
                "posture_events", "environment_events", "reminder_deliveries",
            )
        }

    def test_backup_is_consistent_and_restores_health_data(self):
        self._seed_health_data()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "yu-an.sqlite3"
            self.service.backup_to(backup)

            backup_connection = sqlite3.connect(backup)
            try:
                self.assertEqual("ok", backup_connection.execute("PRAGMA integrity_check").fetchone()[0])
                self.assertEqual(6, backup_connection.execute("PRAGMA user_version").fetchone()[0])
                self.assertEqual(1, backup_connection.execute("SELECT COUNT(*) FROM symptom_entries").fetchone()[0])
                self.assertEqual(1, backup_connection.execute("SELECT COUNT(*) FROM posture_events").fetchone()[0] - 1)
            finally:
                backup_connection.close()

            self.connection.execute("DELETE FROM symptom_entries")
            self.connection.commit()
            self.service.restore_from(backup)
            self.assertEqual(1, self.connection.execute("SELECT COUNT(*) FROM symptom_entries").fetchone()[0])
            self.assertEqual("NEEDS_CONFIRMATION", self.posture.state.posture)
            self.assertIsNone(self.posture.elapsed_seconds())

    def test_invalid_restore_does_not_replace_current_data(self):
        self._seed_health_data()
        before = self._counts()
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.sqlite3"
            invalid.write_bytes(b"not a sqlite database")
            with self.assertRaises((sqlite3.DatabaseError, ValueError)):
                self.service.restore_from(invalid)
        self.assertEqual(before, self._counts())
        self.assertEqual("SITTING", self.posture.state.posture)

    def test_active_database_cannot_be_used_as_backup_or_restore_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assistant.sqlite3"
            connection = open_database(path)
            try:
                service = DataManagementService(connection)
                with self.assertRaises(ValueError):
                    service.backup_to(path)
                with self.assertRaises(ValueError):
                    service.restore_from(path)
            finally:
                connection.close()

    def test_delete_health_records_is_atomic_and_keeps_schema_usable(self):
        self._seed_health_data()
        self.connection.execute(
            "CREATE TRIGGER block_symptom_delete BEFORE DELETE ON symptom_entries "
            "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
        self.connection.commit()
        before = self._counts()
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delete_health_records()
        self.assertEqual(before, self._counts())
        self.assertEqual("SITTING", self.posture.state.posture)

        self.connection.execute("DROP TRIGGER block_symptom_delete")
        self.connection.commit()
        summary = self.service.delete_health_records()
        self.assertEqual(before["symptom_entries"], summary.symptom_entries)
        for table in ("symptom_entries", "exercise_logs", "exercise_plans", "exercises", "environment_events", "reminder_deliveries"):
            self.assertEqual(0, self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], table)
        self.assertEqual(1, self.connection.execute(
            "SELECT COUNT(*) FROM posture_events WHERE event_type='runtime_started'"
        ).fetchone()[0])
        self.assertEqual("UNKNOWN", self.posture.state.posture)
        self.assertEqual(6, self.connection.execute("PRAGMA user_version").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
