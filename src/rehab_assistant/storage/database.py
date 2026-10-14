"""SQLite database bootstrap and explicit schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 4


def migrate(connection: sqlite3.Connection) -> int:
    """Apply pending migrations atomically and return the resulting version."""
    connection.execute("PRAGMA foreign_keys = ON")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema {version} is newer than supported {SCHEMA_VERSION}"
        )

    migrations = {
        1: (
            "CREATE TABLE app_settings ("
            "setting_key TEXT PRIMARY KEY, value_json TEXT NOT NULL, "
            "updated_at_utc TEXT NOT NULL)",
        ),
        2: (
            "CREATE TABLE posture_events ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, "
            "event_type TEXT NOT NULL, occurred_at_utc TEXT NOT NULL, "
            "payload_json TEXT NOT NULL)",
            "CREATE TABLE posture_snapshot ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
            "last_event_seq INTEGER NOT NULL, state_json TEXT NOT NULL)",
        ),
        3: (
            "CREATE TABLE environment_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, "
            "event_type TEXT NOT NULL, occurred_at_utc TEXT NOT NULL, payload_json TEXT NOT NULL)",
            "CREATE TABLE reminder_deliveries ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, "
            "threshold_minutes INTEGER NOT NULL CHECK(threshold_minutes IN (35, 40)), "
            "sequence_no INTEGER NOT NULL DEFAULT 0, scheduled_at_utc TEXT NOT NULL, "
            "status TEXT NOT NULL, channel TEXT, "
            "attempt_count INTEGER NOT NULL DEFAULT 0, last_attempt_at_utc TEXT, "
            "last_error TEXT, seen_at_utc TEXT, "
            "UNIQUE(session_id, threshold_minutes, sequence_no))",
        ),
        4: (
            "CREATE TABLE symptom_entries ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "record_date_local TEXT NOT NULL UNIQUE, "
            "pain_score INTEGER CHECK(pain_score IS NULL OR (pain_score >= 0 AND pain_score <= 10)), "
            "body_locations_json TEXT NOT NULL, "
            "leg_symptoms TEXT NOT NULL, "
            "activity_relation TEXT NOT NULL, "
            "safety_flags_json TEXT NOT NULL, "
            "notes TEXT NOT NULL, "
            "created_at_utc TEXT NOT NULL, "
            "updated_at_utc TEXT NOT NULL)",
        ),
    }
    while version < SCHEMA_VERSION:
        next_version = version + 1
        statements = migrations.get(next_version)
        if statements is None:
            raise RuntimeError(f"Missing migration {next_version}")
        with connection:
            for statement in statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {next_version}")
        version = next_version
    return version


def open_database(path: Path) -> sqlite3.Connection:
    """Open a local database and apply migrations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        migrate(connection)
    except Exception:
        connection.close()
        raise
    return connection
