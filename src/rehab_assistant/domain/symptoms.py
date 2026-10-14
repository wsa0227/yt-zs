"""Validated daily symptom records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


BODY_LOCATIONS = ("下腰部", "左背部", "右背部", "左腿", "右腿", "其他")
LEG_SYMPTOMS = ("未填写", "无新增症状", "新增腿痛", "新增麻木", "新增无力", "多种症状")
ACTIVITY_RELATIONS = ("未知", "坐姿时", "站姿时", "弯腰时", "其他")
SAFETY_FLAGS = (
    "perineal_numbness",
    "urinary_retention",
    "bowel_bladder_change",
    "exercise_worsening",
)
MAX_NOTES_LENGTH = 2000


@dataclass(frozen=True)
class SymptomRecord:
    id: int | None
    record_date_local: str
    pain_score: int | None
    body_locations: tuple[str, ...]
    leg_symptoms: str
    activity_relation: str
    safety_flags: tuple[str, ...]
    notes: str
    created_at_utc: str | None
    updated_at_utc: str | None

    def validate(self) -> "SymptomRecord":
        try:
            parsed_date = date.fromisoformat(self.record_date_local)
        except (TypeError, ValueError) as error:
            raise ValueError("record_date_local must be a valid ISO local date") from error
        if parsed_date.isoformat() != self.record_date_local:
            raise ValueError("record_date_local must use YYYY-MM-DD")
        if self.pain_score is not None and (
            not isinstance(self.pain_score, int) or not 0 <= self.pain_score <= 10
        ):
            raise ValueError("pain_score must be NULL or an integer from 0 to 10")
        locations = tuple(dict.fromkeys(self.body_locations))
        if any(location not in BODY_LOCATIONS for location in locations):
            raise ValueError("body_locations contains an unknown value")
        if self.leg_symptoms not in LEG_SYMPTOMS:
            raise ValueError("leg_symptoms contains an unknown value")
        if self.activity_relation not in ACTIVITY_RELATIONS:
            raise ValueError("activity_relation contains an unknown value")
        flags = tuple(dict.fromkeys(self.safety_flags))
        if any(flag not in SAFETY_FLAGS for flag in flags):
            raise ValueError("safety_flags contains an unknown value")
        if not isinstance(self.notes, str) or len(self.notes) > MAX_NOTES_LENGTH:
            raise ValueError(f"notes must be at most {MAX_NOTES_LENGTH} characters")
        return SymptomRecord(
            id=self.id,
            record_date_local=self.record_date_local,
            pain_score=self.pain_score,
            body_locations=locations,
            leg_symptoms=self.leg_symptoms,
            activity_relation=self.activity_relation,
            safety_flags=flags,
            notes=self.notes,
            created_at_utc=self.created_at_utc,
            updated_at_utc=self.updated_at_utc,
        )
