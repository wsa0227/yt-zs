"""Durable reminder creation, delivery and acknowledgement."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from rehab_assistant.services.posture_service import PostureService


class NotificationChannel(Protocol):
    """A channel that accepts a reminder for delivery."""

    def notify(self, reminder: "Reminder") -> None:
        ...


class ReminderClock(Protocol):
    def now(self) -> datetime:
        ...


class SystemReminderClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Reminder:
    id: int
    session_id: str
    threshold_minutes: int
    sequence_no: int
    scheduled_at_utc: str
    status: str
    channel: str | None
    attempt_count: int
    last_error: str | None
    seen_at_utc: str | None


@dataclass(frozen=True)
class ReminderResult:
    reminder: Reminder
    status: str
    error: str | None = None


class ReminderService:
    """Routes durable reminder facts to an injectable notification channel.

    The database row is created before the channel is called. A successful
    channel call records delivery acceptance only; it never records that the
    user read the reminder.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        posture: PostureService,
        channel: NotificationChannel,
        *,
        clock: ReminderClock | None = None,
        retry_interval_seconds: int = 30,
        channel_name: str = "windows_tray",
    ) -> None:
        self._connection = connection
        self._posture = posture
        self._channel = channel
        self._clock = clock or SystemReminderClock()
        self._retry_interval = max(0, retry_interval_seconds)
        self._channel_name = channel_name

    def evaluate_and_deliver(self) -> tuple[ReminderResult, ...]:
        """Create due rows, then deliver due and retryable pending rows."""
        self._posture.evaluate_reminders()
        self._materialize_due_events()
        results: list[ReminderResult] = []
        for reminder in self.pending_reminders(retryable_only=True):
            self._record_attempt(reminder.id)
            try:
                self._channel.notify(reminder)
            except Exception as error:  # channel failures must remain actionable
                message = str(error) or error.__class__.__name__
                self._record_failure(reminder.id, message)
                results.append(ReminderResult(
                    self._load_reminder(reminder.id), "pending", message
                ))
            else:
                self._record_delivery(reminder.id)
                results.append(ReminderResult(
                    self._load_reminder(reminder.id), "delivered"
                ))
        return tuple(results)

    def pending_reminders(self, *, retryable_only: bool = False) -> tuple[Reminder, ...]:
        clauses = [
            "status = 'pending'" if retryable_only
            else "status IN ('pending', 'delivered')"
        ]
        parameters: list[object] = []
        if retryable_only:
            cutoff = self._clock.now().astimezone(timezone.utc) - timedelta(
                seconds=self._retry_interval
            )
            clauses.append(
                "(attempt_count = 0 OR last_attempt_at_utc IS NULL "
                "OR last_attempt_at_utc <= ?)"
            )
            parameters.append(cutoff.isoformat(timespec="milliseconds"))
        rows = self._connection.execute(
            "SELECT id, session_id, threshold_minutes, sequence_no, "
            "scheduled_at_utc, status, channel, attempt_count, last_error, seen_at_utc "
            "FROM reminder_deliveries WHERE " + " AND ".join(clauses) +
            " ORDER BY id",
            parameters,
        ).fetchall()
        return tuple(self._row_to_reminder(row) for row in rows)

    def acknowledge_seen(self, delivery_id: int) -> Reminder:
        """Record user acknowledgement without changing posture or timing."""
        seen_at = self._utc_now_iso()
        with self._connection:
            self._connection.execute(
                "UPDATE reminder_deliveries SET status='acknowledged', seen_at_utc=?, "
                "last_error=NULL WHERE id=? AND status IN ('pending', 'delivered')",
                (seen_at, delivery_id),
            )
        return self._load_reminder(delivery_id)

    def _materialize_due_events(self) -> None:
        with self._connection:
            for event in self._posture.events:
                if event["event_type"] != "reminder_due":
                    continue
                payload = event["payload"]
                self._connection.execute(
                    "INSERT OR IGNORE INTO reminder_deliveries("
                    "session_id, threshold_minutes, sequence_no, scheduled_at_utc, status, channel) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        payload["session_id"],
                        int(payload["threshold_minutes"]),
                        int(payload.get("sequence_no", 0)),
                        event["occurred_at_utc"],
                        "pending",
                        self._channel_name,
                    ),
                )

    def _record_attempt(self, delivery_id: int) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE reminder_deliveries SET attempt_count=attempt_count+1, "
                "last_attempt_at_utc=?, channel=? WHERE id=? AND status='pending'",
                (self._utc_now_iso(), self._channel_name, delivery_id),
            )

    def _record_failure(self, delivery_id: int, error: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE reminder_deliveries SET status='pending', last_error=? WHERE id=?",
                (error, delivery_id),
            )

    def _record_delivery(self, delivery_id: int) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE reminder_deliveries SET status='delivered', last_error=NULL WHERE id=?",
                (delivery_id,),
            )

    def _load_reminder(self, delivery_id: int) -> Reminder:
        row = self._connection.execute(
            "SELECT id, session_id, threshold_minutes, sequence_no, "
            "scheduled_at_utc, status, channel, attempt_count, last_error, seen_at_utc "
            "FROM reminder_deliveries WHERE id=?",
            (delivery_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Reminder delivery {delivery_id} does not exist")
        return self._row_to_reminder(row)

    @staticmethod
    def _row_to_reminder(row: tuple[object, ...]) -> Reminder:
        return Reminder(
            id=int(row[0]),
            session_id=str(row[1]),
            threshold_minutes=int(row[2]),
            sequence_no=int(row[3]),
            scheduled_at_utc=str(row[4]) if row[4] is not None else "",
            status=str(row[5]),
            channel=str(row[6]) if row[6] is not None else None,
            attempt_count=int(row[7]),
            last_error=str(row[8]) if row[8] is not None else None,
            seen_at_utc=str(row[9]) if row[9] is not None else None,
        )

    def _utc_now_iso(self) -> str:
        return self._clock.now().astimezone(timezone.utc).isoformat(timespec="milliseconds")
