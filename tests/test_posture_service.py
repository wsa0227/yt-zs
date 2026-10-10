import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from rehab_assistant.domain.posture import InvalidTransition
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.storage.database import migrate


class FakeClock:
    def __init__(self):
        self.value = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
        self.ticks = 0.0

    def now(self):
        return self.value

    def monotonic(self):
        return self.ticks

    def advance(self, **kwargs):
        delta = timedelta(**kwargs)
        self.value += delta
        self.ticks += delta.total_seconds()


class PostureServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FakeClock()
        self.service = PostureService(self.connection, self.clock)

    def tearDown(self):
        self.connection.close()

    def test_no_confirmation_means_no_session_or_elapsed_time(self):
        self.clock.advance(minutes=90)
        self.assertEqual("UNKNOWN", self.service.state.posture)
        self.assertEqual((), self.service.evaluate_reminders())

    def test_thresholds_are_exact_and_idempotent(self):
        self.service.confirm_sitting()
        self.clock.advance(minutes=34, seconds=59)
        self.assertEqual((), self.service.evaluate_reminders())
        self.clock.advance(seconds=1)
        self.assertEqual((35,), self.service.evaluate_reminders())
        self.assertEqual((), self.service.evaluate_reminders())
        self.clock.advance(minutes=5)
        self.assertEqual((40,), self.service.evaluate_reminders())
        self.assertEqual((35, 40), self.service.state.pending_reminders)
        self.assertEqual("SITTING", self.service.state.posture)

    def test_wall_clock_jump_does_not_advance_runtime_timer(self):
        self.service.confirm_sitting()
        self.clock.value += timedelta(hours=8)
        self.assertEqual((), self.service.evaluate_reminders())
        self.clock.advance(minutes=35)
        self.assertEqual((35,), self.service.evaluate_reminders())

    def test_manual_up_and_sit_create_separate_cycles(self):
        self.service.confirm_sitting()
        first_id = self.service.state.session_id
        self.clock.advance(minutes=4)
        self.service.confirm_up()
        self.assertIsNone(self.service.state.session_id)
        self.service.confirm_sitting()
        self.assertNotEqual(first_id, self.service.state.session_id)
        self.assertEqual(self.clock.now().isoformat(timespec="milliseconds"), self.service.state.sitting_since)

    def test_invalid_transition_does_not_append_an_event(self):
        self.service.confirm_up()
        count = len(self.service.events)
        with self.assertRaises(InvalidTransition):
            self.service.confirm_up()
        self.assertEqual(count, len(self.service.events))

    def test_event_and_projection_snapshot_commit_together(self):
        self.service.confirm_sitting()
        seq, projection = self.connection.execute(
            "SELECT last_event_seq,state_json FROM posture_snapshot WHERE singleton=1"
        ).fetchone()
        event_count = self.connection.execute("SELECT COUNT(*) FROM posture_events").fetchone()[0]
        self.assertEqual(event_count, seq)
        self.assertIn('"posture":"SITTING"', projection)

    def test_unclosed_runtime_recovers_to_confirmation_and_retains_original_start(self):
        self.service.confirm_sitting()
        original_start = self.service.state.sitting_since
        self.clock.advance(hours=2)
        recovered = PostureService(self.connection, self.clock)
        self.assertEqual("NEEDS_CONFIRMATION", recovered.state.posture)
        self.assertEqual(original_start, recovered.state.sitting_since)
        recovered.reconcile_continue_sitting()
        self.assertEqual("SITTING", recovered.state.posture)
        self.assertTrue(recovered.state.uncertain)
        self.assertEqual(original_start, recovered.state.sitting_since)

    def test_clean_exit_marks_the_gap_for_confirmation_on_next_launch(self):
        self.service.confirm_sitting()
        self.service.close()
        recovered = PostureService(self.connection, self.clock)
        self.assertEqual("NEEDS_CONFIRMATION", recovered.state.posture)

    def test_event_replay_reconstructs_current_projection(self):
        self.service.confirm_sitting()
        self.clock.advance(minutes=35)
        self.service.evaluate_reminders()
        reconstructed = PostureService.__new__(PostureService)
        reconstructed._connection = self.connection
        reconstructed._clock = self.clock
        reconstructed._events = reconstructed._load_events()
        from rehab_assistant.domain.posture import replay
        self.assertEqual(replay(reconstructed._events), self.service.state)

    def test_correction_is_appended_and_replayed_without_deleting_original(self):
        self.service.confirm_up()
        mistaken = self.service.events[-1]["event_id"]
        corrected = self.service.correct_event(mistaken, "confirm_sitting")
        self.assertEqual("SITTING", corrected.posture)
        self.assertEqual("confirm_up", self.service.events[-2]["event_type"])
        self.assertEqual("correction", self.service.events[-1]["event_type"])

    def test_database_failure_does_not_mutate_in_memory_state(self):
        before = self.service.state
        with patch.object(self.service, "_append_and_snapshot", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.service.confirm_sitting()
        self.assertEqual(before, self.service.state)


if __name__ == "__main__":
    unittest.main()
