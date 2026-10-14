"""Deterministic symptom warnings reviewed as product copy, not diagnosis."""

from __future__ import annotations

from dataclasses import dataclass

from rehab_assistant.domain.symptoms import SymptomRecord


@dataclass(frozen=True)
class SafetyAlert:
    code: str
    severity: str
    message: str


_ALERTS = {
    "perineal_numbness": SafetyAlert(
        "perineal_numbness", "emergency",
        "出现会阴或肛周麻木：请及时进行急诊评估。",
    ),
    "urinary_retention": SafetyAlert(
        "urinary_retention", "emergency",
        "出现无法排尿：请及时进行急诊评估。",
    ),
    "bowel_bladder_change": SafetyAlert(
        "bowel_bladder_change", "emergency",
        "出现排尿或排便控制改变：请及时进行急诊评估。",
    ),
    "new_leg_weakness": SafetyAlert(
        "new_leg_weakness", "urgent",
        "出现显著新发或进行性的腿部无力：请尽快联系医疗专业人员评估。",
    ),
    "exercise_worsening": SafetyAlert(
        "exercise_worsening", "urgent",
        "训练后症状明显加重或出现向腿部放射的疼痛、麻木：停止相关训练并联系医疗专业人员评估。",
    ),
}


def evaluate_symptoms(record: SymptomRecord) -> tuple[SafetyAlert, ...]:
    """Return fixed alerts in a stable order; never infer a diagnosis."""
    record = record.validate()
    codes = set(record.safety_flags)
    if record.leg_symptoms == "新增无力":
        codes.add("new_leg_weakness")
    order = (
        "perineal_numbness",
        "urinary_retention",
        "bowel_bladder_change",
        "new_leg_weakness",
        "exercise_worsening",
    )
    return tuple(_ALERTS[code] for code in order if code in codes)
