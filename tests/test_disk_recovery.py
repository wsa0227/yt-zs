import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.storage.database import open_database


class FixedClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        self.ticks = 100.0

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return self.ticks


class DiskRecoveryTests(unittest.TestCase):
    def test_unclean_runtime_recovers_from_disk_wal_without_inventing_elapsed_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assistant.sqlite3"
            clock = FixedClock()

            connection = open_database(path)
            self.assertEqual(
                "wal",
                connection.execute("PRAGMA journal_mode").fetchone()[0].lower(),
            )
            service = PostureService(connection, clock)
            service.confirm_sitting()
            original_start = service.state.sitting_since
            original_event_count = len(service.events)

            # Close only the database connection to model a process ending
            # before PostureService.close() can append runtime_ended.
            connection.close()

            recovered_connection = open_database(path)
            self.assertEqual(
                "wal",
                recovered_connection.execute("PRAGMA journal_mode").fetchone()[0].lower(),
            )
            recovered = PostureService(recovered_connection, clock)

            self.assertEqual("NEEDS_CONFIRMATION", recovered.state.posture)
            self.assertTrue(recovered.state.uncertain)
            self.assertEqual(original_start, recovered.state.sitting_since)
            self.assertIsNone(recovered.elapsed_seconds())
            self.assertEqual(original_event_count + 2, len(recovered.events))
            self.assertEqual(
                "unclean_or_previous_runtime",
                recovered.events[-2]["payload"]["reason"],
            )
            self.assertEqual("runtime_started", recovered.events[-1]["event_type"])
            self.assertEqual(
                original_event_count + 2,
                recovered_connection.execute(
                    "SELECT COUNT(*) FROM posture_events"
                ).fetchone()[0],
            )

            recovered_connection.close()


if __name__ == "__main__":
    unittest.main()
