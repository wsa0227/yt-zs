import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from rehab_assistant.domain.symptoms import SymptomRecord
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.statistics_service import StatisticsService
from rehab_assistant.services.symptom_service import SymptomService
from rehab_assistant.storage.database import migrate


class FixedClock:
    def __init__(self):
        self.value = datetime(2026, 10, 14, 23, 50, tzinfo=timezone.utc)
        self.ticks = 0.0

    def now(self):
        return self.value

    def monotonic(self):
        return self.ticks

    def advance(self, **kwargs):
        delta = timedelta(**kwargs)
        self.value += delta
        self.ticks += delta.total_seconds()


def symptom(record_date, pain_score):
    return SymptomRecord(
        id=None,
        record_date_local=record_date,
        pain_score=pain_score,
        body_locations=("下腰部",),
        leg_symptoms="未填写",
        activity_relation="未知",
        safety_flags=(),
        notes="",
        created_at_utc=None,
        updated_at_utc=None,
    )


class StatisticsServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FixedClock()
        self.posture = PostureService(self.connection, self.clock)
        self.symptoms = SymptomService(self.connection, clock=self.clock)
        self.statistics = StatisticsService(
            self.connection, clock=self.clock, local_timezone=timezone.utc
        )

    def tearDown(self):
        self.connection.close()

    def test_recent_returns_full_calendar_range_and_keeps_missing_values_null(self):
        rows = self.statistics.recent(7)

        self.assertEqual(7, len(rows))
        self.assertEqual("2026-10-08", rows[0].record_date_local)
        self.assertEqual("2026-10-14", rows[-1].record_date_local)
        self.assertIsNone(rows[-1].sitting_seconds)
        self.assertIsNone(rows[-1].up_count)
        self.assertFalse(rows[-1].symptom_recorded)

    def test_confirmed_sitting_is_split_across_local_days(self):
        self.posture.confirm_sitting()
        self.clock.advance(minutes=20)
        self.posture.confirm_up()

        rows = self.statistics.daily("2026-10-14", "2026-10-15")
        self.assertEqual(10 * 60, rows[0].sitting_seconds)
        self.assertEqual(10 * 60, rows[1].sitting_seconds)
        self.assertEqual(1, rows[1].up_count)
        self.assertIsNone(rows[0].up_count)

    def test_interrupted_interval_is_excluded_from_confirmed_duration(self):
        self.posture.confirm_sitting()
        self.clock.advance(minutes=5)
        self.posture.observe_environment("sleep_started")
        self.clock.advance(minutes=30)
        self.posture.reconcile_continue_sitting()
        self.clock.advance(minutes=5)
        self.posture.confirm_up()

        rows = self.statistics.daily("2026-10-14", "2026-10-15")
        self.assertEqual(5 * 60, rows[0].sitting_seconds)
        self.assertEqual(5 * 60, rows[0].uncertain_sitting_seconds)
        self.assertIsNone(rows[0].up_count)
        self.assertIsNone(rows[1].sitting_seconds)
        self.assertEqual(30 * 60, rows[1].uncertain_sitting_seconds)
        self.assertEqual(1, rows[1].up_count)

    def test_symptom_missing_score_is_distinct_from_zero(self):
        self.symptoms.save(symptom("2026-10-13", None))
        self.symptoms.save(symptom("2026-10-14", 0))

        rows = self.statistics.daily("2026-10-12", "2026-10-14")
        self.assertFalse(rows[0].symptom_recorded)
        self.assertTrue(rows[1].symptom_recorded)
        self.assertIsNone(rows[1].pain_score)
        self.assertEqual(0, rows[2].pain_score)

    def test_wall_clock_change_does_not_create_posture_duration(self):
        self.posture.confirm_sitting()
        self.clock.value += timedelta(hours=8)

        row = self.statistics.daily("2026-10-14", "2026-10-15")[0]
        self.assertIsNone(row.sitting_seconds)


if __name__ == "__main__":
    unittest.main()
