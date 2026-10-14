"""Transactional posture commands and reminder threshold evaluation."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from rehab_assistant.domain.posture import (
    PostureState, apply_event, make_event, parse_utc, replay,
)


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()


class PostureService:
    CLOCK_JUMP_TOLERANCE_SECONDS = 120.0

    def __init__(self, connection: sqlite3.Connection, clock: Clock | None = None) -> None:
        self._connection = connection
        self._clock = clock or SystemClock()
        self._events = self._load_events()
        self._state = replay(self._events)
        self._elapsed_base_seconds = 0.0
        self._session_monotonic_anchor: float | None = None
        if self._state.runtime_open:
            self._record("interrupted", {"reason": "unclean_or_previous_runtime"})
        self._record("runtime_started")
        self._last_wall_time = self._clock.now().astimezone(timezone.utc)
        self._last_monotonic = self._clock.monotonic()

    @property
    def state(self) -> PostureState:
        return self._state

    @property
    def events(self) -> tuple[dict, ...]:
        return tuple(self._events)

    def confirm_sitting(self) -> PostureState:
        return self._record("confirm_sitting", {"session_id": str(uuid4())})

    def confirm_up(self) -> PostureState:
        return self._record("confirm_up")

    def confirm_unknown(self) -> PostureState:
        return self._record("confirm_unknown", {
            "basis": "user_report",
            "decision": "unknown",
        })

    def pause(self) -> PostureState:
        return self._record("pause")

    def resume_needs_confirmation(self) -> PostureState:
        return self._record("resume_needs_confirmation")

    def reconcile_continue_sitting(self) -> PostureState:
        return self._record("reconcile_continue_sitting", {
            "basis": "user_report",
            "decision": "continued_sitting",
        })

    def reconcile_up(self) -> PostureState:
        return self._record("reconcile_up", {
            "basis": "user_report",
            "decision": "up",
        })

    def reconcile_unknown(self) -> PostureState:
        return self._record("reconcile_unknown", {
            "basis": "user_report",
            "decision": "unknown",
        })

    def evaluate_reminders(self) -> tuple[int, ...]:
        state = self._state
        if state.posture != "SITTING" or not state.session_id or not state.sitting_since:
            return ()
        if self._session_monotonic_anchor is None:
            return ()
        elapsed = self._elapsed_base_seconds + (
            self._clock.monotonic() - self._session_monotonic_anchor
        )
        if elapsed < 0:
            return ()
        existing = {
            (
                int(event["payload"]["threshold_minutes"]),
                int(event["payload"].get("sequence_no", 0)),
            )
            for event in self._events
            if event["event_type"] == "reminder_due"
            and event["payload"].get("session_id") == state.session_id
        }
        created = []
        schedule = (
            (35, 0, 35),
            (40, 0, 40),
            (40, 1, 45),
            (40, 2, 50),
            (40, 3, 55),
        )
        for threshold, sequence_no, due_minutes in schedule:
            key = (threshold, sequence_no)
            if elapsed >= due_minutes * 60 and key not in existing:
                self._record("reminder_due", {
                    "session_id": state.session_id,
                    "threshold_minutes": threshold,
                    "sequence_no": sequence_no,
                })
                created.append(threshold)
        return tuple(created)

    def elapsed_seconds(self) -> int | None:
        if self._state.posture != "SITTING" or self._session_monotonic_anchor is None:
            return None
        return max(0, int(
            self._elapsed_base_seconds + self._clock.monotonic() - self._session_monotonic_anchor
        ))

    def check_clock_consistency(self, *, tolerance_seconds: float | None = None) -> bool:
        """Detect wall-clock jumps without using wall time for elapsed sitting time.

        A significant divergence between wall time and the monotonic source is
        persisted as an environment fact. If the user was sitting or up, the
        existing interruption flow moves the posture to confirmation instead
        of silently extending or clearing the current session.
        """
        current_wall = self._clock.now().astimezone(timezone.utc)
        current_monotonic = self._clock.monotonic()
        wall_delta = (current_wall - self._last_wall_time).total_seconds()
        monotonic_delta = current_monotonic - self._last_monotonic
        self._last_wall_time = current_wall
        self._last_monotonic = current_monotonic
        tolerance = (
            self.CLOCK_JUMP_TOLERANCE_SECONDS
            if tolerance_seconds is None else max(0.0, float(tolerance_seconds))
        )
        drift = wall_delta - monotonic_delta
        if abs(drift) <= tolerance:
            return False
        self.observe_environment("clock_jump", {
            "wall_delta_seconds": wall_delta,
            "monotonic_delta_seconds": monotonic_delta,
            "drift_seconds": drift,
        })
        return True

    def observe_environment(self, event_type: str, payload: dict | None = None) -> PostureState:
        """Persist an OS fact; only evidence-breaking events create a pending gap."""
        occurred_at = self._clock.now()
        environment_payload = dict(payload or {})
        environment_event = make_event(event_type, occurred_at, environment_payload)
        interruption_types = {"session_locked", "sleep_started", "clock_jump"}
        posture_event = None
        next_state = self._state
        if event_type in interruption_types and self._state.posture in ("SITTING", "UP"):
            posture_event = make_event("interrupted", occurred_at, {
                "reason": event_type,
                "environment_event_id": environment_event["event_id"],
                **environment_payload,
            })
            next_state = apply_event(
                self._state,
                posture_event["event_type"],
                posture_event["occurred_at_utc"],
                posture_event["payload"],
            )
        with self._connection:
            self._connection.execute(
                "INSERT INTO environment_events(event_id,event_type,occurred_at_utc,payload_json) "
                "VALUES(?,?,?,?)",
                (environment_event["event_id"], environment_event["event_type"],
                 environment_event["occurred_at_utc"], json.dumps(
                     environment_event["payload"], separators=(",", ":"), sort_keys=True)),
            )
            if posture_event is not None:
                self._insert_posture_event(posture_event, next_state)
        if posture_event is not None:
            self._events.append(posture_event)
            self._state = next_state
            self._elapsed_base_seconds = 0.0
            self._session_monotonic_anchor = None
        return self._state

    def correct_event(self, target_event_id: str, replacement_type: str) -> PostureState:
        allowed = {
            "confirm_sitting", "confirm_up", "confirm_unknown", "pause",
            "resume_needs_confirmation", "reconcile_up", "reconcile_unknown",
        }
        target = next((event for event in self._events if event["event_id"] == target_event_id), None)
        if target is None or target["event_type"] not in allowed:
            raise ValueError("Correction target must be an existing posture command")
        if replacement_type not in allowed:
            raise ValueError("Unsupported correction command")
        payload = dict(target["payload"])
        if replacement_type == "confirm_sitting" and "session_id" not in payload:
            payload["session_id"] = str(uuid4())
        proposed = [*self._events, make_event("correction", self._clock.now(), {
            "target_event_id": target_event_id,
            "replacement_type": replacement_type,
            "replacement_payload": payload,
        })]
        next_state = replay(proposed)
        self._append_and_snapshot(proposed[-1], next_state)
        self._events = proposed
        self._state = next_state
        return next_state

    def close(self) -> None:
        if self._state.runtime_open:
            self._record("runtime_ended")

    def reload_from_storage(self, *, force: bool = False) -> PostureState:
        """Rebuild state after an external database restore.

        ``force`` is used when the caller knows that another database table
        changed even though the posture event stream did not. Ordinary
        repeated refreshes remain idempotent.
        """
        loaded_events = self._load_events()
        if not force and loaded_events == self._events:
            # A repeated refresh without a new restore must not manufacture
            # another interruption fact. Reset the volatile clock anchors,
            # though, because the caller may have restored the database file
            # outside this service between refresh attempts.
            self._elapsed_base_seconds = 0.0
            self._session_monotonic_anchor = None
            self._last_wall_time = self._clock.now().astimezone(timezone.utc)
            self._last_monotonic = self._clock.monotonic()
            return self._state

        self._events = loaded_events
        self._state = replay(self._events)
        self._elapsed_base_seconds = 0.0
        self._session_monotonic_anchor = None
        if self._state.runtime_open:
            self._record("interrupted", {"reason": "database_restore"})
        if not self._state.runtime_open:
            self._record("runtime_started")
        self._last_wall_time = self._clock.now().astimezone(timezone.utc)
        self._last_monotonic = self._clock.monotonic()
        return self._state

    def reset_history(self) -> PostureState:
        """Delete posture/environment/reminder history and start a fresh runtime."""
        with self._connection:
            self._connection.execute("DELETE FROM reminder_deliveries")
            self._connection.execute("DELETE FROM environment_events")
            self._connection.execute("DELETE FROM posture_events")
            self._connection.execute("DELETE FROM posture_snapshot")
        self._events = []
        self._state = PostureState(runtime_open=False)
        self._elapsed_base_seconds = 0.0
        self._session_monotonic_anchor = None
        state = self._record("runtime_started")
        self._last_wall_time = self._clock.now().astimezone(timezone.utc)
        self._last_monotonic = self._clock.monotonic()
        return state

    def _record(self, event_type: str, payload: dict | None = None) -> PostureState:
        event = make_event(event_type, self._clock.now(), payload)
        next_state = apply_event(self._state, event_type, event["occurred_at_utc"], event["payload"])
        self._append_and_snapshot(event, next_state)
        self._events.append(event)
        self._state = next_state
        if event_type == "confirm_sitting":
            self._elapsed_base_seconds = 0.0
            self._session_monotonic_anchor = self._clock.monotonic()
        elif event_type == "reconcile_continue_sitting":
            self._elapsed_base_seconds = max(
                0.0,
                (self._clock.now().astimezone(timezone.utc) - parse_utc(next_state.sitting_since)).total_seconds(),
            )
            self._session_monotonic_anchor = self._clock.monotonic()
        elif event_type in ("confirm_up", "resume_needs_confirmation", "reconcile_unknown"):
            self._elapsed_base_seconds = 0.0
            self._session_monotonic_anchor = None
        return next_state

    def _load_events(self) -> list[dict]:
        rows = self._connection.execute(
            "SELECT event_id, event_type, occurred_at_utc, payload_json "
            "FROM posture_events ORDER BY seq"
        ).fetchall()
        return [
            {"event_id": row[0], "event_type": row[1], "occurred_at_utc": row[2],
             "payload": json.loads(row[3])}
            for row in rows
        ]

    def _append_and_snapshot(self, event: dict, state: PostureState) -> None:
        with self._connection:
            self._insert_posture_event(event, state)

    def _insert_posture_event(self, event: dict, state: PostureState) -> None:
        cursor = self._connection.execute(
            "INSERT INTO posture_events(event_id,event_type,occurred_at_utc,payload_json) "
            "VALUES(?,?,?,?)",
            (event["event_id"], event["event_type"], event["occurred_at_utc"],
             json.dumps(event["payload"], separators=(",", ":"), sort_keys=True)),
        )
        self._connection.execute(
            "INSERT INTO posture_snapshot(singleton,last_event_seq,state_json) VALUES(1,?,?) "
            "ON CONFLICT(singleton) DO UPDATE SET last_event_seq=excluded.last_event_seq, "
            "state_json=excluded.state_json",
            (cursor.lastrowid, json.dumps(asdict(state), separators=(",", ":"), sort_keys=True)),
        )
