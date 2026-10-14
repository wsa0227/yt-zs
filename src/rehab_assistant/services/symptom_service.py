"""Transactional persistence and local CSV export for daily symptom records."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from rehab_assistant.domain.symptoms import SymptomRecord


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SymptomService:
    def __init__(self, connection: sqlite3.Connection, clock: Clock | None = None):
        self._connection = connection
        self._clock = clock or SystemClock()

    def save(self, record: SymptomRecord) -> SymptomRecord:
        record = record.validate()
        now = self._utc_now_iso()
        with self._connection:
            existing = self._find_existing(record)
            if existing is None:
                created_at = record.created_at_utc or now
                cursor = self._connection.execute(
                    "INSERT INTO symptom_entries("
                    "record_date_local, pain_score, body_locations_json, leg_symptoms, "
                    "activity_relation, safety_flags_json, notes, created_at_utc, updated_at_utc) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    self._values(record, created_at, now),
                )
                record_id = int(cursor.lastrowid)
            else:
                record_id = existing.id
                created_at = existing.created_at_utc or record.created_at_utc or now
                self._connection.execute(
                    "UPDATE symptom_entries SET record_date_local=?, pain_score=?, "
                    "body_locations_json=?, leg_symptoms=?, activity_relation=?, "
                    "safety_flags_json=?, notes=?, created_at_utc=?, updated_at_utc=? "
                    "WHERE id=?",
                    self._values(record, created_at, now) + (record_id,),
                )
        return SymptomRecord(
            id=record_id,
            record_date_local=record.record_date_local,
            pain_score=record.pain_score,
            body_locations=record.body_locations,
            leg_symptoms=record.leg_symptoms,
            activity_relation=record.activity_relation,
            safety_flags=record.safety_flags,
            notes=record.notes,
            created_at_utc=created_at,
            updated_at_utc=now,
        )

    def get_by_id(self, record_id: int) -> SymptomRecord | None:
        row = self._connection.execute(
            "SELECT id, record_date_local, pain_score, body_locations_json, leg_symptoms, "
            "activity_relation, safety_flags_json, notes, created_at_utc, updated_at_utc "
            "FROM symptom_entries WHERE id=?",
            (record_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def get_by_date(self, record_date_local: str) -> SymptomRecord | None:
        self._validate_date(record_date_local)
        row = self._connection.execute(
            "SELECT id, record_date_local, pain_score, body_locations_json, leg_symptoms, "
            "activity_relation, safety_flags_json, notes, created_at_utc, updated_at_utc "
            "FROM symptom_entries WHERE record_date_local=?",
            (record_date_local,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list_records(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> tuple[SymptomRecord, ...]:
        self._validate_optional_dates(start_date, end_date)
        clauses = []
        values: list[str] = []
        if start_date:
            clauses.append("record_date_local >= ?")
            values.append(start_date)
        if end_date:
            clauses.append("record_date_local <= ?")
            values.append(end_date)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            "SELECT id, record_date_local, pain_score, body_locations_json, leg_symptoms, "
            "activity_relation, safety_flags_json, notes, created_at_utc, updated_at_utc "
            "FROM symptom_entries" + where + " ORDER BY record_date_local DESC, id DESC",
            values,
        ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def delete(self, record_id: int) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM symptom_entries WHERE id=?", (record_id,))

    def count(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM symptom_entries").fetchone()[0])

    def export_csv(
        self, path: str | Path, start_date: str | None = None, end_date: str | None = None
    ) -> int:
        records = tuple(reversed(self.list_records(start_date, end_date)))
        target = Path(path)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "record_date_local", "pain_score", "body_locations", "leg_symptoms",
                "activity_relation", "safety_flags", "notes", "created_at_utc", "updated_at_utc",
            ))
            writer.writeheader()
            for record in records:
                writer.writerow({
                    "record_date_local": record.record_date_local,
                    "pain_score": "" if record.pain_score is None else record.pain_score,
                    "body_locations": "、".join(record.body_locations),
                    "leg_symptoms": record.leg_symptoms,
                    "activity_relation": record.activity_relation,
                    "safety_flags": ",".join(record.safety_flags),
                    "notes": record.notes,
                    "created_at_utc": record.created_at_utc or "",
                    "updated_at_utc": record.updated_at_utc or "",
                })
        return len(records)

    def _find_existing(self, record: SymptomRecord) -> SymptomRecord | None:
        if record.id is not None:
            existing = self.get_by_id(record.id)
            if existing is None:
                raise LookupError(f"Symptom record {record.id} does not exist")
            return existing
        return self.get_by_date(record.record_date_local)

    @staticmethod
    def _values(record: SymptomRecord, created_at: str, updated_at: str) -> tuple[object, ...]:
        return (
            record.record_date_local,
            record.pain_score,
            json.dumps(record.body_locations, ensure_ascii=False),
            record.leg_symptoms,
            record.activity_relation,
            json.dumps(record.safety_flags, ensure_ascii=False),
            record.notes,
            created_at,
            updated_at,
        )

    @staticmethod
    def _row_to_record(row: tuple[object, ...]) -> SymptomRecord:
        return SymptomRecord(
            id=int(row[0]),
            record_date_local=str(row[1]),
            pain_score=int(row[2]) if row[2] is not None else None,
            body_locations=tuple(json.loads(str(row[3]))),
            leg_symptoms=str(row[4]),
            activity_relation=str(row[5]),
            safety_flags=tuple(json.loads(str(row[6]))),
            notes=str(row[7]),
            created_at_utc=str(row[8]),
            updated_at_utc=str(row[9]),
        ).validate()

    @staticmethod
    def _validate_date(value: str) -> None:
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise ValueError("date must be a valid ISO local date") from error
        if parsed.isoformat() != value:
            raise ValueError("date must use YYYY-MM-DD")

    def _validate_optional_dates(self, start_date: str | None, end_date: str | None) -> None:
        if start_date:
            self._validate_date(start_date)
        if end_date:
            self._validate_date(end_date)
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must not be after end_date")

    def _utc_now_iso(self) -> str:
        return self._clock.now().astimezone(timezone.utc).isoformat(timespec="milliseconds")
