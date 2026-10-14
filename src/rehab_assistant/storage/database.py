"""SQLite database bootstrap and explicit schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 6


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
        5: (
            "CREATE TABLE exercises ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, "
            "source_url TEXT NOT NULL, "
            "source_org TEXT NOT NULL, "
            "content TEXT NOT NULL, "
            "contraindication_notes TEXT NOT NULL, "
            "reviewer TEXT, "
            "approved_at_utc TEXT, "
            "status TEXT NOT NULL CHECK(status IN ('CANDIDATE', 'APPROVED', 'SUSPENDED')), "
            "created_at_utc TEXT NOT NULL, "
            "updated_at_utc TEXT NOT NULL, "
            "CHECK(status != 'APPROVED' OR (reviewer IS NOT NULL AND reviewer != '' "
            "AND approved_at_utc IS NOT NULL))"
            ")",
            "CREATE TABLE exercise_plans ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "exercise_id INTEGER NOT NULL UNIQUE REFERENCES exercises(id), "
            "status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'STOPPED')), "
            "added_at_utc TEXT NOT NULL, "
            "stopped_at_utc TEXT, "
            "stop_reason TEXT NOT NULL DEFAULT ''"
            ")",
            "CREATE TABLE exercise_logs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "exercise_id INTEGER NOT NULL REFERENCES exercises(id), "
            "performed_at_utc TEXT NOT NULL, "
            "completed INTEGER NOT NULL CHECK(completed IN (0, 1)), "
            "user_response TEXT NOT NULL, "
            "symptom_change TEXT NOT NULL, "
            "notes TEXT NOT NULL"
            ")",
        ),
        6: (
            "ALTER TABLE exercises ADD COLUMN catalog_id TEXT",
            "ALTER TABLE exercises ADD COLUMN category TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE exercises ADD COLUMN review_questions_json TEXT NOT NULL DEFAULT '[]'",
            "CREATE UNIQUE INDEX exercises_catalog_id_unique "
            "ON exercises(catalog_id) WHERE catalog_id IS NOT NULL",
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
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(f"SQLite integrity check failed: {integrity}")
        connection.execute("PRAGMA journal_mode = WAL")
        migrate(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(f"SQLite integrity check failed: {integrity}")
    except Exception:
        connection.close()
        raise
    return connection
