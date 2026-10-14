import sqlite3
import unittest
from datetime import datetime, timezone

from rehab_assistant.domain.exercises import ExerciseRecord
from rehab_assistant.services.exercise_service import ExerciseService
from rehab_assistant.storage.database import migrate


class FixedClock:
    def __init__(self):
        self.value = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)

    def now(self):
        return self.value


def candidate(**changes):
    values = dict(
        id=None,
        name="医生提供的动作资料",
        source_url="https://example.invalid/material",
        source_org="专业人员提供",
        content="按专业人员给出的图文或视频说明执行。",
        contraindication_notes="如有不适立即停止并联系专业人员。",
        reviewer=None,
        approved_at_utc=None,
        status="CANDIDATE",
        created_at_utc=None,
        updated_at_utc=None,
    )
    values.update(changes)
    return ExerciseRecord(**values)


class ExerciseServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FixedClock()
        self.service = ExerciseService(self.connection, self.clock)

    def tearDown(self):
        self.connection.close()

    def test_migration_creates_catalog_plan_and_log_tables(self):
        tables = {
            row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertTrue({"exercises", "exercise_plans", "exercise_logs"} <= tables)
        migrate(self.connection)

    def test_candidate_is_not_executable_or_addable_to_plan(self):
        record = self.service.save_candidate(candidate())
        self.assertEqual((record,), self.service.list_exercises("CANDIDATE"))
        self.assertEqual((), self.service.list_executable())
        with self.assertRaises(ValueError):
            self.service.add_to_plan(record.id)
        self.assertEqual((), self.service.list_plans())

    def test_approval_requires_reviewer_and_then_allows_plan(self):
        record = self.service.save_candidate(candidate())
        with self.assertRaises(ValueError):
            self.service.approve(record.id, "")
        approved = self.service.approve(record.id, "康复治疗师", "2026-10-14T08:01:00+00:00")
        self.assertEqual("APPROVED", approved.status)
        self.assertEqual("康复治疗师", approved.reviewer)
        plan = self.service.add_to_plan(record.id)
        self.assertEqual("ACTIVE", plan.status)
        self.assertEqual(plan, self.service.add_to_plan(record.id))

    def test_suspending_exercise_stops_active_plan_and_cannot_reactivate(self):
        record = self.service.save_candidate(candidate())
        self.service.approve(record.id, "康复治疗师")
        self.service.add_to_plan(record.id)
        suspended = self.service.suspend(record.id, "专业人员要求暂时停用")
        self.assertEqual("SUSPENDED", suspended.status)
        plan = self.service.get_plan(record.id)
        self.assertEqual("STOPPED", plan.status)
        self.assertEqual("专业人员要求暂时停用", plan.stop_reason)
        with self.assertRaises(ValueError):
            self.service.add_to_plan(record.id)

    def test_approval_and_suspension_are_state_limited(self):
        record = self.service.save_candidate(candidate())
        self.service.approve(record.id, "康复治疗师")
        with self.assertRaises(ValueError):
            self.service.approve(record.id, "另一位专业人员")
        self.service.suspend(record.id)
        with self.assertRaises(ValueError):
            self.service.approve(record.id, "康复治疗师")

    def test_logs_preserve_discomfort_and_missing_symptom_change(self):
        record = self.service.save_candidate(candidate())
        log = self.service.record_log(
            record.id,
            completed=False,
            user_response="出现不适，已停止",
            symptom_change="症状加重",
            notes="停止后记录，等待专业人员评估。",
        )
        self.assertFalse(log.completed)
        self.assertEqual("症状加重", log.symptom_change)
        self.assertEqual((log,), self.service.list_logs(record.id))

    def test_write_failure_does_not_report_approval_or_stop(self):
        record = self.service.save_candidate(candidate())
        self.connection.execute(
            "CREATE TRIGGER fail_exercise_update BEFORE UPDATE ON exercises "
            "BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.approve(record.id, "康复治疗师")
        self.assertEqual("CANDIDATE", self.service.get_by_id(record.id).status)


if __name__ == "__main__":
    unittest.main()
