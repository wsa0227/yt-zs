import csv
import io
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from rehab_assistant.domain.symptoms import SymptomRecord
from rehab_assistant.safety.symptom_rules import evaluate_symptoms
from rehab_assistant.services.symptom_service import SymptomService
from rehab_assistant.storage.database import migrate


class FixedClock:
    def __init__(self):
        self.value = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)

    def now(self):
        return self.value


def make_record(**changes):
    values = dict(
        id=None,
        created_at_utc=None,
        updated_at_utc=None,
        record_date_local="2026-10-14",
        pain_score=None,
        body_locations=("下腰部",),
        leg_symptoms="未填写",
        activity_relation="未知",
        safety_flags=(),
        notes="",
    )
    values.update(changes)
    return SymptomRecord(**values)


class SymptomServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FixedClock()
        self.service = SymptomService(self.connection, clock=self.clock)

    def tearDown(self):
        self.connection.close()

    def test_migration_creates_symptoms_table_and_is_idempotent(self):
        migrate(self.connection)
        columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(symptom_entries)")
        }
        self.assertTrue({"record_date_local", "pain_score", "safety_flags_json"} <= columns)

    def test_save_edit_and_list_preserve_null_and_zero(self):
        missing = self.service.save(make_record())
        zero = self.service.save(make_record(record_date_local="2026-10-15", pain_score=0))
        self.assertIsNone(missing.pain_score)
        self.assertEqual(0, zero.pain_score)

        edited = self.service.save(make_record(
            id=missing.id,
            pain_score=7,
            notes="编辑后的备注",
            safety_flags=("urinary_retention",),
        ))
        self.assertEqual(missing.id, edited.id)
        self.assertEqual(7, self.service.get_by_date("2026-10-14").pain_score)
        self.assertEqual("编辑后的备注", self.service.get_by_id(missing.id).notes)
        self.assertEqual(2, len(self.service.list_records()))

    def test_invalid_values_are_rejected_before_write(self):
        with self.assertRaises(ValueError):
            self.service.save(make_record(pain_score=-1))
        with self.assertRaises(ValueError):
            self.service.save(make_record(pain_score=11))
        with self.assertRaises(ValueError):
            self.service.save(make_record(record_date_local="2026-02-30"))
        self.assertEqual(0, self.service.count())

    def test_delete_removes_record(self):
        record = self.service.save(make_record())
        self.service.delete(record.id)
        self.assertIsNone(self.service.get_by_id(record.id))
        self.assertEqual((), self.service.list_records())

    def test_csv_export_is_utf8_and_keeps_missing_score_empty(self):
        self.service.save(make_record())
        self.service.save(make_record(record_date_local="2026-10-15", pain_score=0))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "symptoms.csv"
            self.assertEqual(2, self.service.export_csv(path))
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            self.assertEqual("", rows[0]["pain_score"])
            self.assertEqual("0", rows[1]["pain_score"])

    def test_save_failure_does_not_report_success_or_change_existing_record(self):
        record = self.service.save(make_record(notes="原备注"))
        self.connection.execute(
            "CREATE TRIGGER fail_symptom_update BEFORE UPDATE ON symptom_entries "
            "BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.save(make_record(id=record.id, notes="不应写入"))
        self.assertEqual("原备注", self.service.get_by_id(record.id).notes)


class SymptomRulesTests(unittest.TestCase):
    def test_emergency_flags_return_fixed_alerts(self):
        alerts = evaluate_symptoms(make_record(
            safety_flags=("perineal_numbness", "urinary_retention", "bowel_bladder_change"),
        ))
        self.assertEqual(
            {"perineal_numbness", "urinary_retention", "bowel_bladder_change"},
            {alert.code for alert in alerts},
        )
        self.assertTrue(all("急诊评估" in alert.message for alert in alerts))

    def test_new_leg_weakness_and_training_worsening_are_not_silent(self):
        alerts = evaluate_symptoms(make_record(
            leg_symptoms="新增无力",
            safety_flags=("exercise_worsening",),
        ))
        self.assertEqual({"new_leg_weakness", "exercise_worsening"}, {a.code for a in alerts})

    def test_ordinary_back_pain_does_not_trigger_alert(self):
        self.assertEqual((), evaluate_symptoms(make_record(pain_score=6)))


if __name__ == "__main__":
    unittest.main()
