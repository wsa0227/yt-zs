"""Deterministic posture state machine; environment signals never alter posture."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class InvalidTransition(ValueError):
    pass


@dataclass(frozen=True)
class PostureState:
    posture: str = "UNKNOWN"
    session_id: str | None = None
    sitting_since: str | None = None
    uncertain: bool = False
    runtime_open: bool = False
    pending_reminders: tuple[int, ...] = ()


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def apply_event(state: PostureState, event_type: str, at: str, payload: dict[str, Any]) -> PostureState:
    if event_type == "runtime_started":
        return replace(state, runtime_open=True)
    if event_type == "runtime_ended":
        if state.posture in ("SITTING", "UP"):
            state = replace(state, posture="NEEDS_CONFIRMATION", uncertain=True)
        return replace(state, runtime_open=False)
    if event_type == "interrupted":
        if state.posture in ("SITTING", "UP"):
            return replace(state, posture="NEEDS_CONFIRMATION", uncertain=True)
        return state
    if event_type == "confirm_sitting":
        if state.posture not in ("UNKNOWN", "UP"):
            raise InvalidTransition(f"Cannot confirm sitting from {state.posture}")
        return PostureState(
            posture="SITTING", session_id=payload["session_id"], sitting_since=at,
            runtime_open=state.runtime_open,
        )
    if event_type == "confirm_up":
        if state.posture not in ("UNKNOWN", "SITTING", "NEEDS_CONFIRMATION"):
            raise InvalidTransition(f"Cannot confirm standing from {state.posture}")
        return replace(state, posture="UP", session_id=None, sitting_since=None, uncertain=False)
    if event_type == "confirm_unknown":
        if state.posture not in ("UNKNOWN", "UP"):
            raise InvalidTransition(f"Cannot leave posture unknown from {state.posture}")
        return PostureState(posture="UNKNOWN", runtime_open=state.runtime_open)
    if event_type == "pause":
        if state.posture == "PAUSED":
            raise InvalidTransition("Tracking is already paused")
        return replace(state, posture="PAUSED")
    if event_type == "resume_needs_confirmation":
        if state.posture != "PAUSED":
            raise InvalidTransition("Tracking is not paused")
        return PostureState(posture="UNKNOWN", runtime_open=state.runtime_open)
    if event_type == "reconcile_continue_sitting":
        if state.posture != "NEEDS_CONFIRMATION":
            raise InvalidTransition("There is no interrupted sitting period to reconcile")
        return replace(state, posture="SITTING", uncertain=True)
    if event_type == "reconcile_up":
        if state.posture != "NEEDS_CONFIRMATION":
            raise InvalidTransition("There is no interrupted period to reconcile")
        return replace(state, posture="UP", session_id=None, sitting_since=None, uncertain=False)
    if event_type == "reconcile_unknown":
        if state.posture != "NEEDS_CONFIRMATION":
            raise InvalidTransition("There is no interrupted period to reconcile")
        return PostureState(posture="UNKNOWN", runtime_open=state.runtime_open)
    if event_type == "reminder_due":
        threshold = int(payload["threshold_minutes"])
        if state.posture == "SITTING" and threshold not in state.pending_reminders:
            return replace(state, pending_reminders=state.pending_reminders + (threshold,))
        return state
    raise ValueError(f"Unknown posture event: {event_type}")


def replay(events: list[dict[str, Any]]) -> PostureState:
    replacements = {
        event["payload"]["target_event_id"]: event["payload"]
        for event in events if event["event_type"] == "correction"
    }
    state = PostureState()
    for event in events:
        kind = event["event_type"]
        if kind == "correction":
            continue
        payload = event["payload"]
        if event["event_id"] in replacements:
            correction = replacements[event["event_id"]]
            kind, payload = correction["replacement_type"], correction["replacement_payload"]
        state = apply_event(state, kind, event["occurred_at_utc"], payload)
    return state


def make_event(event_type: str, occurred_at: datetime, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "occurred_at_utc": utc_iso(occurred_at),
        "payload": payload or {},
    }
