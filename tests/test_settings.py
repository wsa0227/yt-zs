import sqlite3
import unittest
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from rehab_assistant.services.settings_service import SettingsService
from rehab_assistant.storage.database import migrate
from test_reminders import FakeClock, RecordingChannel


class SettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.settings = SettingsService(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_defaults_are_safe_and_round_trip(self):
        self.assertEqual((True, True), (
            self.settings.reminder_preferences().sound_enabled,
            self.settings.reminder_preferences().followups_enabled,
        ))

        self.settings.set_reminder_sound_enabled(False)
        self.settings.set_reminder_followups_enabled(False)

        reopened = SettingsService(self.connection)
        self.assertEqual((False, False), (
            reopened.reminder_preferences().sound_enabled,
            reopened.reminder_preferences().followups_enabled,
        ))

    def test_invalid_json_falls_back_without_coercion(self):
        self.connection.execute(
            "INSERT INTO app_settings(setting_key,value_json,updated_at_utc) VALUES(?,?,?)",
            (SettingsService.REMINDER_FOLLOWUPS_KEY, '"false"', "now"),
        )
        self.assertTrue(self.settings.reminder_preferences().followups_enabled)

    def test_non_boolean_write_is_rejected(self):
        with self.assertRaises(TypeError):
            self.settings.set_reminder_followups_enabled(1)


class ReminderPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        migrate(self.connection)
        self.clock = FakeClock()
        self.posture = PostureService(self.connection, self.clock)
        self.posture.confirm_sitting()
        self.settings = SettingsService(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_disabling_followups_keeps_only_first_thresholds(self):
        self.settings.set_reminder_followups_enabled(False)
        channel = RecordingChannel()
        reminders = ReminderService(
            self.connection, self.posture, channel,
            clock=self.clock, retry_interval_seconds=0, settings=self.settings,
        )
        self.clock.advance(minutes=55)

        reminders.evaluate_and_deliver()

        self.assertEqual([(35, 0), (40, 0)], [
            (item.threshold_minutes, item.sequence_no) for item in channel.reminders
        ])
        self.assertEqual(
            [(0, "delivered"), (0, "delivered"), (1, "suppressed"),
             (2, "suppressed"), (3, "suppressed")],
            self.connection.execute(
                "SELECT sequence_no,status FROM reminder_deliveries ORDER BY sequence_no"
            ).fetchall(),
        )

    def test_suppressed_followups_are_not_replayed_after_reenable(self):
        self.settings.set_reminder_followups_enabled(False)
        channel = RecordingChannel()
        reminders = ReminderService(
            self.connection, self.posture, channel,
            clock=self.clock, retry_interval_seconds=0, settings=self.settings,
        )
        self.clock.advance(minutes=55)
        reminders.evaluate_and_deliver()
        self.settings.set_reminder_followups_enabled(True)
        self.clock.advance(minutes=5)

        reminders.evaluate_and_deliver()

        self.assertEqual([(35, 0), (40, 0)], [
            (item.threshold_minutes, item.sequence_no) for item in channel.reminders
        ])

    def test_disabling_followups_does_not_hide_already_delivered_reminder(self):
        channel = RecordingChannel()
        reminders = ReminderService(
            self.connection, self.posture, channel,
            clock=self.clock, retry_interval_seconds=0, settings=self.settings,
        )
        self.clock.advance(minutes=50)
        reminders.evaluate_and_deliver()
        self.settings.set_reminder_followups_enabled(False)

        delivered_followup = next(
            item for item in reminders.pending_reminders()
            if item.sequence_no == 1
        )

        self.assertEqual("delivered", delivered_followup.status)
        self.assertEqual("acknowledged", reminders.acknowledge_seen(delivered_followup.id).status)


if __name__ == "__main__":
    unittest.main()
