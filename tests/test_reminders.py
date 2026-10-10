import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
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


class RecordingChannel:
    def __init__(self, connection=None, *, fail=False):
        self.connection = connection
        self.fail = fail
        self.reminders = []
        self.rows_seen_at_notify = []

    def notify(self, reminder):
        if self.connection is not None:
            self.rows_seen_at_notify.append(self.connection.execute(
                "SELECT status, attempt_count FROM reminder_deliveries WHERE id=?",
                (reminder.id,),
            ).fetchone())
        if self.fail:
            raise RuntimeError("notification unavailable")
        self.reminders.append(reminder)


class ReminderServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FakeClock()
        self.posture = PostureService(self.connection, self.clock)
        self.posture.confirm_sitting()

    def tearDown(self):
        self.connection.close()

    def test_delivery_is_persisted_before_channel_and_is_idempotent(self):
        channel = RecordingChannel(self.connection)
        reminders = ReminderService(
            self.connection, self.posture, channel, clock=self.clock, retry_interval_seconds=0
        )
        self.clock.advance(minutes=35)

        results = reminders.evaluate_and_deliver()
        self.assertEqual(("pending", 1), channel.rows_seen_at_notify[0])
        self.assertEqual(("delivered",), tuple(result.status for result in results))
        self.assertEqual(1, len(channel.reminders))
        self.assertEqual(1, len(reminders.pending_reminders()))
        self.assertEqual((), reminders.evaluate_and_deliver())
        self.assertEqual(1, self.connection.execute(
            "SELECT COUNT(*) FROM reminder_deliveries"
        ).fetchone()[0])

    def test_failed_delivery_remains_pending_and_can_retry(self):
        channel = RecordingChannel(fail=True)
        reminders = ReminderService(
            self.connection, self.posture, channel, clock=self.clock, retry_interval_seconds=0
        )
        self.clock.advance(minutes=40)

        results = reminders.evaluate_and_deliver()
        self.assertEqual(("pending", "pending"), tuple(result.status for result in results))
        row = self.connection.execute(
            "SELECT status, attempt_count, last_error FROM reminder_deliveries "
            "WHERE threshold_minutes=40 AND sequence_no=0"
        ).fetchone()
        self.assertEqual(("pending", 1, "notification unavailable"), row)

        channel.fail = False
        retry_results = reminders.evaluate_and_deliver()
        self.assertEqual(("delivered", "delivered"), tuple(result.status for result in retry_results))
        self.assertEqual(2, retry_results[-1].reminder.attempt_count)

    def test_acknowledgement_does_not_change_posture_or_end_session(self):
        channel = RecordingChannel()
        reminders = ReminderService(self.connection, self.posture, channel, clock=self.clock)
        self.clock.advance(minutes=35)
        reminders.evaluate_and_deliver()
        delivery = reminders.pending_reminders()[0]
        before = self.posture.state

        acknowledged = reminders.acknowledge_seen(delivery.id)

        self.assertEqual("acknowledged", acknowledged.status)
        self.assertEqual(before, self.posture.state)
        self.assertEqual((), reminders.pending_reminders())

    def test_forty_minute_followups_are_bounded_and_idempotent(self):
        channel = RecordingChannel()
        reminders = ReminderService(self.connection, self.posture, channel, clock=self.clock)
        self.clock.advance(minutes=55)

        reminders.evaluate_and_deliver()
        self.assertEqual(
            [(35, 0), (40, 0), (40, 1), (40, 2), (40, 3)],
            [(item.threshold_minutes, item.sequence_no) for item in channel.reminders],
        )
        reminders.evaluate_and_deliver()
        self.assertEqual(5, len(channel.reminders))
        self.assertEqual(5, self.connection.execute(
            "SELECT COUNT(*) FROM reminder_deliveries"
        ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
