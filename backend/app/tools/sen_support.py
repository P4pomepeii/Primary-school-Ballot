"""SEN / school-programme lookup tool.

Backed by the curated schools.json seed for now. Swap `_load_schools` for a
real database call once you have curated data — the function signature is
the MCP tool contract, keep it stable.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..schema import ChildProfile, SchoolFitEvidence

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "schools.json"


@lru_cache(maxsize=1)
def _load_schools() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_school_ids() -> list[str]:
    return [s["id"] for s in _load_schools()["schools"]]


def get_school(school_id: str) -> dict | None:
    for s in _load_schools()["schools"]:
        if s["id"] == school_id:
            return s
    return None


def sen_fit_score(profile: ChildProfile, school: dict) -> float:
    """Crude, explainable scoring — replace with something better once you
    have real labeled outcomes, but keep it interpretable. Each rule below
    is something you can say out loud to a parent.
    """
    sen = school["sen_support"]
    if not profile.sen_conditions and not profile.sensory_preferences:
        return 0.6  # neutral — no SEN need stated, don't penalize or reward

    score = 0.0
    weight_total = 0.0

    if sen.get("learning_support_programme"):
        score += 1.0
    weight_total += 1.0

    aeb = sen.get("allied_educators_learning_behavioural", 0)
    score += min(aeb / 3, 1.0)
    weight_total += 1.0

    if any("dyslexia" in c.lower() for c in profile.sen_conditions) and sen.get(
        "dyslexia_specific_resourcing"
    ):
        score += 1.0
        weight_total += 1.0

    if profile.sensory_preferences and "sensory" in sen.get("notes", "").lower():
        score += 1.0
        weight_total += 1.0

    return round(score / weight_total, 2) if weight_total else 0.5


def sen_support_tool(profile: ChildProfile, school_id: str) -> SchoolFitEvidence:
    school = get_school(school_id)
    if school is None:
        raise ValueError(f"Unknown school_id: {school_id}")

    score = sen_fit_score(profile, school)
    sen = school["sen_support"]
    summary_bits = []
    if sen.get("learning_support_programme"):
        summary_bits.append("has a Learning Support Programme")
    if sen.get("allied_educators_learning_behavioural"):
        summary_bits.append(
            f"{sen['allied_educators_learning_behavioural']} allied educator(s) for learning/behavioural support"
        )
    if sen.get("dyslexia_specific_resourcing"):
        summary_bits.append("dyslexia-specific resourcing")
    summary = "; ".join(summary_bits) if summary_bits else "no structured SEN programme reported"

    concern = None
    if score < 0.4:
        concern = "Limited documented SEN support relative to the stated needs — verify directly with the school."

    return SchoolFitEvidence(
        school_id=school_id,
        source="sen_support",
        summary=f"{school['name']}: {summary}. {sen.get('notes', '')}".strip(),
        concern=concern,
        score_0_to_1=score,
        citation="Seed dataset — replace with curated school SEN pages before production use.",
    )
