"""Validated user-entered rehabilitation material and activity logs."""

from __future__ import annotations

from dataclasses import dataclass


EXERCISE_STATUSES = ("CANDIDATE", "APPROVED", "SUSPENDED")
PLAN_STATUSES = ("ACTIVE", "STOPPED")
SYMPTOM_CHANGES = ("未填写", "无明显变化", "症状减轻", "症状加重", "出现放射或麻木")
MAX_NAME_LENGTH = 120
MAX_SOURCE_URL_LENGTH = 2048
MAX_SOURCE_ORG_LENGTH = 200
MAX_CONTENT_LENGTH = 10000
MAX_NOTES_LENGTH = 2000


@dataclass(frozen=True)
class ExerciseRecord:
    id: int | None
    name: str
    source_url: str
    source_org: str
    content: str
    contraindication_notes: str
    reviewer: str | None
    approved_at_utc: str | None
    status: str
    created_at_utc: str | None
    updated_at_utc: str | None

    def validate(self) -> "ExerciseRecord":
        name = self.name.strip() if isinstance(self.name, str) else ""
        source_url = self.source_url.strip() if isinstance(self.source_url, str) else ""
        source_org = self.source_org.strip() if isinstance(self.source_org, str) else ""
        content = self.content.strip() if isinstance(self.content, str) else ""
        cautions = (
            self.contraindication_notes.strip()
            if isinstance(self.contraindication_notes, str)
            else ""
        )
        reviewer = self.reviewer.strip() if isinstance(self.reviewer, str) else None
        if not name or len(name) > MAX_NAME_LENGTH:
            raise ValueError(f"name must be 1-{MAX_NAME_LENGTH} characters")
        if len(source_url) > MAX_SOURCE_URL_LENGTH:
            raise ValueError(f"source_url must be at most {MAX_SOURCE_URL_LENGTH} characters")
        if not source_org or len(source_org) > MAX_SOURCE_ORG_LENGTH:
            raise ValueError(f"source_org must be 1-{MAX_SOURCE_ORG_LENGTH} characters")
        if not content or len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"content must be 1-{MAX_CONTENT_LENGTH} characters")
        if len(cautions) > MAX_NOTES_LENGTH:
            raise ValueError(f"contraindication_notes must be at most {MAX_NOTES_LENGTH} characters")
        if self.status not in EXERCISE_STATUSES:
            raise ValueError("status is not a supported exercise status")
        if self.status == "APPROVED" and (not reviewer or not self.approved_at_utc):
            raise ValueError("approved exercises require reviewer and approved_at_utc")
        return ExerciseRecord(
            id=self.id,
            name=name,
            source_url=source_url,
            source_org=source_org,
            content=content,
            contraindication_notes=cautions,
            reviewer=reviewer or None,
            approved_at_utc=self.approved_at_utc,
            status=self.status,
            created_at_utc=self.created_at_utc,
            updated_at_utc=self.updated_at_utc,
        )


@dataclass(frozen=True)
class ExercisePlan:
    id: int
    exercise_id: int
    status: str
    added_at_utc: str
    stopped_at_utc: str | None
    stop_reason: str

    def validate(self) -> "ExercisePlan":
        if self.status not in PLAN_STATUSES:
            raise ValueError("status is not a supported plan status")
        if self.status == "STOPPED" and not self.stopped_at_utc:
            raise ValueError("stopped plans require stopped_at_utc")
        return self


@dataclass(frozen=True)
class ExerciseLog:
    id: int
    exercise_id: int
    performed_at_utc: str
    completed: bool
    user_response: str
    symptom_change: str
    notes: str

    def validate(self) -> "ExerciseLog":
        if not isinstance(self.completed, bool):
            raise ValueError("completed must be a boolean")
        if not isinstance(self.user_response, str) or not self.user_response.strip():
            raise ValueError("user_response is required")
        if self.symptom_change not in SYMPTOM_CHANGES:
            raise ValueError("symptom_change is not supported")
        if not isinstance(self.notes, str) or len(self.notes) > MAX_NOTES_LENGTH:
            raise ValueError(f"notes must be at most {MAX_NOTES_LENGTH} characters")
        return ExerciseLog(
            id=self.id,
            exercise_id=self.exercise_id,
            performed_at_utc=self.performed_at_utc,
            completed=self.completed,
            user_response=self.user_response.strip(),
            symptom_change=self.symptom_change,
            notes=self.notes,
        )
