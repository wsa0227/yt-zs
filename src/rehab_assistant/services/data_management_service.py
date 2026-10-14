"""Consistent local backup, restore, and health-record deletion."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.storage.database import SCHEMA_VERSION, migrate


@dataclass(frozen=True)
class DeletionSummary:
    symptom_entries: int
    exercise_logs: int
    exercise_plans: int
    exercises: int
    posture_events: int
    environment_events: int
    reminders: int


class DataManagementService:
    """Own file/database safety rules used by the settings page."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        posture_service: PostureService | None = None,
    ) -> None:
        self._connection = connection
        self._posture = posture_service

    def backup_to(self, path: str | Path) -> Path:
        destination = Path(path)
        self._validate_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._temporary_path(destination)
        try:
            target = sqlite3.connect(temporary)
            try:
                self._connection.backup(target)
                self._validate_database(target)
            finally:
                target.close()
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination

    def restore_from(self, path: str | Path) -> Path:
        source_path = Path(path)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        self._reject_live_database(source_path)
        source = sqlite3.connect(source_path)
        temporary = self._temporary_path(source_path)
        candidate = None
        try:
            self._validate_database(source)
            candidate = sqlite3.connect(temporary)
            source.backup(candidate)
            migrate(candidate)
            self._validate_database(candidate)
            candidate.backup(self._connection)
            self._connection.commit()
        finally:
            source.close()
            if candidate is not None:
                candidate.close()
            if temporary.exists():
                temporary.unlink()
        if self._posture is not None:
            self._posture.reload_from_storage(force=True)
        return source_path

    def delete_health_records(self) -> DeletionSummary:
        counts = {
            "symptom_entries": self._count("symptom_entries"),
            "exercise_logs": self._count("exercise_logs"),
            "exercise_plans": self._count("exercise_plans"),
            "exercises": self._count("exercises"),
            "posture_events": self._count("posture_events"),
            "environment_events": self._count("environment_events"),
            "reminders": self._count("reminder_deliveries"),
        }
        with self._connection:
            self._connection.execute("DELETE FROM reminder_deliveries")
            self._connection.execute("DELETE FROM environment_events")
            self._connection.execute("DELETE FROM posture_events")
            self._connection.execute("DELETE FROM posture_snapshot")
            self._connection.execute("DELETE FROM exercise_logs")
            self._connection.execute("DELETE FROM exercise_plans")
            self._connection.execute("DELETE FROM exercises")
            self._connection.execute("DELETE FROM symptom_entries")
        if self._posture is not None:
            # Rebuild only after the cross-table delete has committed. This keeps
            # a failed delete from leaving the in-memory projection out of sync.
            self._posture.reload_from_storage()
        return DeletionSummary(**counts)

    def _validate_database(self, connection: sqlite3.Connection) -> None:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"SQLite integrity check failed: {integrity}")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version <= 0 or version > SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported database schema version {version}; expected 1-{SCHEMA_VERSION}"
            )

    def _validate_destination(self, destination: Path) -> None:
        if destination.exists() and destination.is_dir():
            raise IsADirectoryError(destination)
        self._reject_live_database(destination)

    def _reject_live_database(self, path: Path) -> None:
        rows = self._connection.execute("PRAGMA database_list").fetchall()
        live_paths = {Path(str(row[2])).resolve() for row in rows if row[2]}
        if path.resolve() in live_paths:
            raise ValueError("Backup or restore path must not be the active database")

    @staticmethod
    def _temporary_path(reference: Path) -> Path:
        handle, name = tempfile.mkstemp(
            prefix=f".{reference.stem}.", suffix=".tmp", dir=reference.parent
        )
        os.close(handle)
        path = Path(name)
        path.unlink()
        return path

    def _count(self, table: str) -> int:
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
