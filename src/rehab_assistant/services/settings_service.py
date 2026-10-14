"""Validated application preferences backed by the local SQLite database."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ReminderPreferences:
    """User preferences that affect reminder delivery."""

    sound_enabled: bool = True
    followups_enabled: bool = True


class SettingsService:
    """Read and write typed settings without leaking JSON or SQL to callers."""

    REMINDER_SOUND_KEY = "reminder_sound_enabled"
    REMINDER_FOLLOWUPS_KEY = "reminder_followups_enabled"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def reminder_preferences(self) -> ReminderPreferences:
        return ReminderPreferences(
            sound_enabled=self._read_bool(self.REMINDER_SOUND_KEY, True),
            followups_enabled=self._read_bool(self.REMINDER_FOLLOWUPS_KEY, True),
        )

    def set_reminder_sound_enabled(self, enabled: bool) -> ReminderPreferences:
        self._write_bool(self.REMINDER_SOUND_KEY, enabled)
        return self.reminder_preferences()

    def set_reminder_followups_enabled(self, enabled: bool) -> ReminderPreferences:
        self._write_bool(self.REMINDER_FOLLOWUPS_KEY, enabled)
        return self.reminder_preferences()

    def _read_bool(self, key: str, default: bool) -> bool:
        row = self._connection.execute(
            "SELECT value_json FROM app_settings WHERE setting_key=?", (key,)
        ).fetchone()
        if row is None:
            return default
        try:
            value = json.loads(str(row[0]))
        except (TypeError, json.JSONDecodeError):
            return default
        # bool is deliberately exact: JSON numbers and strings are not settings.
        return value if type(value) is bool else default

    def _write_bool(self, key: str, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError(f"Setting {key} must be a bool")
        updated_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with self._connection:
            self._connection.execute(
                "INSERT INTO app_settings(setting_key, value_json, updated_at_utc) "
                "VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET "
                "value_json=excluded.value_json, updated_at_utc=excluded.updated_at_utc",
                (key, json.dumps(value), updated_at),
            )
