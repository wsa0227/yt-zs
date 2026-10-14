"""Transactional local catalog, plan and log service for user-entered exercises."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Protocol

from rehab_assistant.domain.exercises import ExerciseLog, ExercisePlan, ExerciseRecord


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class ExerciseService:
    """Keep medical-content approval explicit and separate from execution state."""

    def __init__(self, connection: sqlite3.Connection, clock: Clock | None = None):
        self._connection = connection
        self._clock = clock or SystemClock()

    def save_candidate(self, record: ExerciseRecord) -> ExerciseRecord:
        record = record.validate()
        if record.status != "CANDIDATE":
            raise ValueError("only candidate records can be created or edited")
        now = self._utc_now_iso()
        with self._connection:
            if record.id is None:
                cursor = self._connection.execute(
                    "INSERT INTO exercises(name, source_url, source_org, content, "
                    "contraindication_notes, reviewer, approved_at_utc, status, "
                    "created_at_utc, updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    self._exercise_values(record, now, now),
                )
                record_id = int(cursor.lastrowid)
                created_at = now
            else:
                existing = self.get_by_id(record.id)
                if existing is None:
                    raise LookupError(f"Exercise {record.id} does not exist")
                if existing.status != "CANDIDATE":
                    raise ValueError("approved or suspended exercises cannot be edited as candidates")
                self._connection.execute(
                    "UPDATE exercises SET name=?, source_url=?, source_org=?, content=?, "
                    "contraindication_notes=?, reviewer=?, approved_at_utc=?, status=?, "
                    "created_at_utc=?, updated_at_utc=? WHERE id=?",
                    self._exercise_values(record, existing.created_at_utc or now, now)
                    + (record.id,),
                )
                record_id = record.id
                created_at = existing.created_at_utc or now
        return self.get_by_id(record_id) or self._with_timestamps(record, created_at, now, record_id)

    def approve(
        self, exercise_id: int, reviewer: str, approved_at_utc: str | None = None
    ) -> ExerciseRecord:
        reviewer = reviewer.strip() if isinstance(reviewer, str) else ""
        if not reviewer:
            raise ValueError("reviewer is required to approve an exercise")
        existing = self._require(exercise_id)
        if existing.status != "CANDIDATE":
            raise ValueError("only candidate exercises can be approved")
        approved_at = approved_at_utc or self._utc_now_iso()
        now = self._utc_now_iso()
        with self._connection:
            self._connection.execute(
                "UPDATE exercises SET reviewer=?, approved_at_utc=?, status='APPROVED', "
                "updated_at_utc=? WHERE id=?",
                (reviewer, approved_at, now, exercise_id),
            )
        return self._require(exercise_id)

    def suspend(self, exercise_id: int, reason: str = "") -> ExerciseRecord:
        existing = self._require(exercise_id)
        if existing.status == "SUSPENDED":
            return existing
        now = self._utc_now_iso()
        reason = reason.strip()
        with self._connection:
            self._connection.execute(
                "UPDATE exercises SET status='SUSPENDED', updated_at_utc=? WHERE id=?",
                (now, exercise_id),
            )
            self._connection.execute(
                "UPDATE exercise_plans SET status='STOPPED', stopped_at_utc=?, stop_reason=? "
                "WHERE exercise_id=? AND status='ACTIVE'",
                (now, reason or "资料已停用", exercise_id),
            )
        return self._require(exercise_id)

    def get_by_id(self, exercise_id: int) -> ExerciseRecord | None:
        row = self._connection.execute(
            "SELECT id, name, source_url, source_org, content, contraindication_notes, "
            "reviewer, approved_at_utc, status, created_at_utc, updated_at_utc "
            "FROM exercises WHERE id=?",
            (exercise_id,),
        ).fetchone()
        return self._row_to_exercise(row) if row else None

    def list_exercises(self, status: str | None = None) -> tuple[ExerciseRecord, ...]:
        if status is not None and status not in ("CANDIDATE", "APPROVED", "SUSPENDED"):
            raise ValueError("unsupported exercise status")
        clause = " WHERE status=?" if status else ""
        values = (status,) if status else ()
        rows = self._connection.execute(
            "SELECT id, name, source_url, source_org, content, contraindication_notes, "
            "reviewer, approved_at_utc, status, created_at_utc, updated_at_utc "
            "FROM exercises" + clause + " ORDER BY updated_at_utc DESC, id DESC",
            values,
        ).fetchall()
        return tuple(self._row_to_exercise(row) for row in rows)

    def list_executable(self) -> tuple[ExerciseRecord, ...]:
        return self.list_exercises("APPROVED")

    def add_to_plan(self, exercise_id: int) -> ExercisePlan:
        exercise = self._require(exercise_id)
        if exercise.status != "APPROVED":
            raise ValueError("only professionally confirmed exercises can enter a plan")
        existing = self.get_plan(exercise_id)
        if existing is not None:
            if existing.status == "ACTIVE":
                return existing
            raise ValueError("a stopped plan cannot be reactivated")
        now = self._utc_now_iso()
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO exercise_plans(exercise_id, status, added_at_utc) VALUES(?, 'ACTIVE', ?)",
                (exercise_id, now),
            )
        return self.get_plan(exercise_id) or ExercisePlan(
            int(cursor.lastrowid), exercise_id, "ACTIVE", now, None, ""
        )

    def get_plan(self, exercise_id: int) -> ExercisePlan | None:
        row = self._connection.execute(
            "SELECT id, exercise_id, status, added_at_utc, stopped_at_utc, stop_reason "
            "FROM exercise_plans WHERE exercise_id=?",
            (exercise_id,),
        ).fetchone()
        return self._row_to_plan(row) if row else None

    def list_plans(self, active_only: bool = False) -> tuple[ExercisePlan, ...]:
        clause = " WHERE status='ACTIVE'" if active_only else ""
        rows = self._connection.execute(
            "SELECT id, exercise_id, status, added_at_utc, stopped_at_utc, stop_reason "
            "FROM exercise_plans" + clause + " ORDER BY added_at_utc DESC, id DESC"
        ).fetchall()
        return tuple(self._row_to_plan(row) for row in rows)

    def stop_plan(self, exercise_id: int, reason: str = "用户主动停止") -> ExercisePlan:
        plan = self.get_plan(exercise_id)
        if plan is None:
            raise LookupError(f"Exercise {exercise_id} is not in the plan")
        if plan.status == "STOPPED":
            return plan
        now = self._utc_now_iso()
        with self._connection:
            self._connection.execute(
                "UPDATE exercise_plans SET status='STOPPED', stopped_at_utc=?, stop_reason=? WHERE id=?",
                (now, reason.strip() or "用户主动停止", plan.id),
            )
        return self.get_plan(exercise_id)  # type: ignore[return-value]

    def record_log(
        self,
        exercise_id: int,
        *,
        completed: bool,
        user_response: str,
        symptom_change: str = "未填写",
        notes: str = "",
        performed_at_utc: str | None = None,
    ) -> ExerciseLog:
        self._require(exercise_id)
        now = performed_at_utc or self._utc_now_iso()
        candidate = ExerciseLog(
            id=0,
            exercise_id=exercise_id,
            performed_at_utc=now,
            completed=completed,
            user_response=user_response,
            symptom_change=symptom_change,
            notes=notes,
        ).validate()
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO exercise_logs(exercise_id, performed_at_utc, completed, "
                "user_response, symptom_change, notes) VALUES(?,?,?,?,?,?)",
                (exercise_id, now, int(candidate.completed), candidate.user_response,
                 candidate.symptom_change, candidate.notes),
            )
        return ExerciseLog(
            id=int(cursor.lastrowid),
            exercise_id=exercise_id,
            performed_at_utc=now,
            completed=candidate.completed,
            user_response=candidate.user_response,
            symptom_change=candidate.symptom_change,
            notes=candidate.notes,
        )

    def list_logs(self, exercise_id: int | None = None) -> tuple[ExerciseLog, ...]:
        clause = " WHERE exercise_id=?" if exercise_id is not None else ""
        values = (exercise_id,) if exercise_id is not None else ()
        rows = self._connection.execute(
            "SELECT id, exercise_id, performed_at_utc, completed, user_response, "
            "symptom_change, notes FROM exercise_logs" + clause
            + " ORDER BY performed_at_utc DESC, id DESC",
            values,
        ).fetchall()
        return tuple(self._row_to_log(row) for row in rows)

    def _require(self, exercise_id: int) -> ExerciseRecord:
        record = self.get_by_id(exercise_id)
        if record is None:
            raise LookupError(f"Exercise {exercise_id} does not exist")
        return record

    @staticmethod
    def _exercise_values(record: ExerciseRecord, created_at: str, updated_at: str) -> tuple[object, ...]:
        return (
            record.name, record.source_url, record.source_org, record.content,
            record.contraindication_notes, record.reviewer, record.approved_at_utc,
            record.status, created_at, updated_at,
        )

    @staticmethod
    def _with_timestamps(record, created_at: str, updated_at: str, record_id: int):
        return ExerciseRecord(
            id=record_id, name=record.name, source_url=record.source_url,
            source_org=record.source_org, content=record.content,
            contraindication_notes=record.contraindication_notes,
            reviewer=record.reviewer, approved_at_utc=record.approved_at_utc,
            status=record.status, created_at_utc=created_at, updated_at_utc=updated_at,
        ).validate()

    @staticmethod
    def _row_to_exercise(row) -> ExerciseRecord:
        return ExerciseRecord(
            id=int(row[0]), name=str(row[1]), source_url=str(row[2]), source_org=str(row[3]),
            content=str(row[4]), contraindication_notes=str(row[5]),
            reviewer=str(row[6]) if row[6] is not None else None,
            approved_at_utc=str(row[7]) if row[7] is not None else None,
            status=str(row[8]), created_at_utc=str(row[9]), updated_at_utc=str(row[10]),
        ).validate()

    @staticmethod
    def _row_to_plan(row) -> ExercisePlan:
        return ExercisePlan(
            id=int(row[0]), exercise_id=int(row[1]), status=str(row[2]),
            added_at_utc=str(row[3]), stopped_at_utc=str(row[4]) if row[4] else None,
            stop_reason=str(row[5]),
        ).validate()

    @staticmethod
    def _row_to_log(row) -> ExerciseLog:
        return ExerciseLog(
            id=int(row[0]), exercise_id=int(row[1]), performed_at_utc=str(row[2]),
            completed=bool(row[3]), user_response=str(row[4]),
            symptom_change=str(row[5]), notes=str(row[6]),
        ).validate()

    def _utc_now_iso(self) -> str:
        return self._clock.now().astimezone(timezone.utc).isoformat(timespec="milliseconds")
