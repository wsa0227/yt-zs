"""Read-only daily statistics contracts.

Statistics deliberately distinguish missing values from measured zeroes.  A
missing posture interval is not evidence that the user sat for zero minutes,
and a missing symptom score is not evidence of no pain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyStatistics:
    """Aggregates for one local calendar day.

    ``None`` means that the metric has no corresponding evidence in the local
    database.  ``0`` remains a valid measured value, for example a confirmed
    sitting interval with zero elapsed seconds or an explicitly recorded pain
    score of zero.
    """

    record_date_local: str
    sitting_seconds: int | None
    uncertain_sitting_seconds: int | None
    up_count: int | None
    pain_score: int | None
    symptom_recorded: bool

    def validate(self) -> "DailyStatistics":
        try:
            parsed = date.fromisoformat(self.record_date_local)
        except (TypeError, ValueError) as error:
            raise ValueError("record_date_local must be a valid ISO local date") from error
        if parsed.isoformat() != self.record_date_local:
            raise ValueError("record_date_local must use YYYY-MM-DD")
        for name, value in (
            ("sitting_seconds", self.sitting_seconds),
            ("uncertain_sitting_seconds", self.uncertain_sitting_seconds),
            ("up_count", self.up_count),
        ):
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be NULL or a non-negative integer")
        if self.pain_score is not None and not 0 <= self.pain_score <= 10:
            raise ValueError("pain_score must be NULL or an integer from 0 to 10")
        if not isinstance(self.symptom_recorded, bool):
            raise ValueError("symptom_recorded must be boolean")
        return self
