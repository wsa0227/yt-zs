import sqlite3
import unittest

from rehab_assistant.storage.database import SCHEMA_VERSION, migrate


class DatabaseMigrationTests(unittest.TestCase):
    def test_new_database_migrates_and_is_idempotent(self):
        connection = sqlite3.connect(":memory:")
        self.assertEqual(SCHEMA_VERSION, migrate(connection))
        self.assertEqual(SCHEMA_VERSION, migrate(connection))
        self.assertEqual(
            [("app_settings",)],
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='app_settings'"
            ).fetchall(),
        )
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertTrue({"environment_events", "reminder_deliveries"} <= tables)
        columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(reminder_deliveries)"
            ).fetchall()
        }
        self.assertIn("scheduled_at_utc", columns)

    def test_reminder_delivery_key_is_unique(self):
        connection = sqlite3.connect(":memory:")
        migrate(connection)
        values = ("session", 35, 0, "2026-10-10T08:35:00.000+00:00", "pending", "test")
        connection.execute(
            "INSERT INTO reminder_deliveries(session_id, threshold_minutes, sequence_no, "
            "scheduled_at_utc, status, channel) VALUES(?,?,?,?,?,?)",
            values,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO reminder_deliveries(session_id, threshold_minutes, sequence_no, "
                "scheduled_at_utc, status, channel) VALUES(?,?,?,?,?,?)",
                values,
            )

    def test_newer_database_is_rejected(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        with self.assertRaises(RuntimeError):
            migrate(connection)

    def test_failed_migration_does_not_advance_version(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY)")
        with self.assertRaises(sqlite3.OperationalError):
            migrate(connection)
        self.assertEqual(0, connection.execute("PRAGMA user_version").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
