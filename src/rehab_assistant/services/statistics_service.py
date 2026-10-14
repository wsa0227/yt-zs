"""Conservative local statistics derived from persisted posture and symptom facts."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Protocol

from rehab_assistant.domain.statistics import DailyStatistics


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class _Interval:
    start: datetime
    end: datetime
    kind: str


class StatisticsService:
    """Build daily read models without inventing posture or symptom evidence.

    The posture event log only contains manual confirmations and evidence-
    breaking environment events.  Confirmed durations stop at the first
    interruption.  The interval after an interruption is exposed separately
    as uncertain and never folded into the confirmed sitting total.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        clock: Clock | None = None,
        local_timezone: tzinfo | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or SystemClock()
        self._timezone = local_timezone or datetime.now().astimezone().tzinfo or timezone.utc

    def recent(self, days: int) -> tuple[DailyStatistics, ...]:
        if days not in (7, 30):
            raise ValueError("days must be 7 or 30")
        end = self._local_date(self._clock.now())
        return self.daily(end - timedelta(days=days - 1), end)

    def daily(self, start_date: str | date, end_date: str | date) -> tuple[DailyStatistics, ...]:
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        if start > end:
            raise ValueError("start_date must not be after end_date")

        days = [start + timedelta(days=index) for index in range((end - start).days + 1)]
        known: defaultdict[str, float] = defaultdict(float)
        uncertain: defaultdict[str, float] = defaultdict(float)
        known_seen: set[str] = set()
        uncertain_seen: set[str] = set()
        up_counts: defaultdict[str, int] = defaultdict(int)
        up_seen: set[str] = set()

        events = self._effective_events()
        for event in events:
            if event["event_type"] == "confirm_up":
                event_date = self._local_date(self._parse_utc(event["occurred_at_utc"]))
                if start <= event_date <= end:
                    up_counts[event_date.isoformat()] += 1
                    up_seen.add(event_date.isoformat())

        for interval in self._posture_intervals(events, self._clock.now()):
            self._split_interval(
                interval,
                start,
                end,
                known,
                uncertain,
                known_seen,
                uncertain_seen,
            )

        symptom_values = self._symptoms(start.isoformat(), end.isoformat())
        result = []
        for current in days:
            key = current.isoformat()
            result.append(DailyStatistics(
                record_date_local=key,
                sitting_seconds=round(known[key]) if key in known_seen else None,
                uncertain_sitting_seconds=round(uncertain[key]) if key in uncertain_seen else None,
                up_count=up_counts[key] if key in up_seen else None,
                pain_score=symptom_values.get(key, (None, False))[0],
                symptom_recorded=symptom_values.get(key, (None, False))[1],
            ).validate())
        return tuple(result)

    def _effective_events(self) -> list[dict]:
        rows = self._connection.execute(
            "SELECT event_id, event_type, occurred_at_utc, payload_json "
            "FROM posture_events ORDER BY seq"
        ).fetchall()
        import json

        events = [
            {
                "event_id": row[0],
                "event_type": row[1],
                "occurred_at_utc": row[2],
                "payload": json.loads(row[3]),
            }
            for row in rows
        ]
        replacements = {
            event["payload"]["target_event_id"]: event["payload"]
            for event in events
            if event["event_type"] == "correction"
        }
        effective = []
        for event in events:
            if event["event_type"] == "correction":
                continue
            replacement = replacements.get(event["event_id"])
            if replacement:
                effective.append({
                    **event,
                    "event_type": replacement["replacement_type"],
                    "payload": replacement["replacement_payload"],
                })
            else:
                effective.append(event)
        return effective

    def _posture_intervals(self, events: list[dict], now: datetime) -> tuple[_Interval, ...]:
        intervals: list[_Interval] = []
        active_start: datetime | None = None
        active_kind: str | None = None
        unknown_start: datetime | None = None

        def close_active(at: datetime) -> None:
            nonlocal active_start, active_kind
            if active_start is not None and at >= active_start and active_kind is not None:
                intervals.append(_Interval(active_start, at, active_kind))
            active_start = None
            active_kind = None

        def close_unknown(at: datetime) -> None:
            nonlocal unknown_start
            if unknown_start is not None and at >= unknown_start:
                intervals.append(_Interval(unknown_start, at, "uncertain"))
            unknown_start = None

        for event in events:
            at = self._parse_utc(event["occurred_at_utc"])
            kind = event["event_type"]
            if kind == "confirm_sitting":
                if unknown_start is not None:
                    close_unknown(at)
                if active_start is not None:
                    close_active(at)
                active_start, active_kind = at, "known"
            elif kind in ("interrupted", "runtime_ended"):
                if active_start is not None:
                    close_active(at)
                    unknown_start = at
                elif unknown_start is None:
                    unknown_start = at
            elif kind == "reconcile_continue_sitting":
                # Keep the uncertainty open from the interruption itself.  A
                # continuation confirmation says the user believes they kept
                # sitting, but it does not establish when that became true.
                # The whole unresolved span therefore remains uncertain until
                # a later manual boundary closes it.
                if unknown_start is None and active_start is not None:
                    close_active(at)
                    unknown_start = at
            elif kind == "reconcile_unknown":
                close_active(at)
                close_unknown(at)
            elif kind == "confirm_up":
                close_active(at)
                close_unknown(at)
            elif kind in ("pause", "resume_needs_confirmation"):
                close_active(at)
                close_unknown(at)

        # An open interval has no reliable end.  Do not extend it to the wall
        # clock: after a restart or clock jump that would turn an unverified
        # period into fabricated sitting time.  It becomes reportable only
        # after a later manual confirmation closes the interval.
        del now
        return tuple(interval for interval in intervals if interval.end > interval.start)

    def _split_interval(
        self,
        interval: _Interval,
        start_date: date,
        end_date: date,
        known: defaultdict[str, float],
        uncertain: defaultdict[str, float],
        known_seen: set[str],
        uncertain_seen: set[str],
    ) -> None:
        cursor = interval.start.astimezone(self._timezone)
        end = interval.end.astimezone(self._timezone)
        while cursor < end:
            current_date = cursor.date()
            next_midnight = datetime.combine(
                current_date + timedelta(days=1), time.min, tzinfo=self._timezone
            )
            chunk_end = min(end, next_midnight)
            if start_date <= current_date <= end_date:
                seconds = (chunk_end - cursor).total_seconds()
                key = current_date.isoformat()
                if interval.kind == "known":
                    known[key] += seconds
                    known_seen.add(key)
                else:
                    uncertain[key] += seconds
                    uncertain_seen.add(key)
            cursor = chunk_end

    def _symptoms(self, start_date: str, end_date: str) -> dict[str, tuple[int | None, bool]]:
        rows = self._connection.execute(
            "SELECT record_date_local, pain_score FROM symptom_entries "
            "WHERE record_date_local >= ? AND record_date_local <= ?",
            (start_date, end_date),
        ).fetchall()
        return {str(row[0]): (int(row[1]) if row[1] is not None else None, True) for row in rows}

    def _local_date(self, value: datetime) -> date:
        return self._ensure_aware(value).astimezone(self._timezone).date()

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return StatisticsService._ensure_aware(parsed).astimezone(timezone.utc)

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @staticmethod
    def _parse_date(value: str | date) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            parsed = date.fromisoformat(str(value))
        except (TypeError, ValueError) as error:
            raise ValueError("date must be a valid ISO local date") from error
        if parsed.isoformat() != value:
            raise ValueError("date must use YYYY-MM-DD")
        return parsed
