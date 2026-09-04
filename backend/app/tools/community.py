"""Community-experience tool (RAG stub).

IMPORTANT — do not skip this before demo day: the entries below are
synthetic placeholders, clearly labeled as such. Do NOT scrape real forum/FB
group posts into this file without consent — that's the one component of
this whole system you cannot fake or shortcut, per PDPA (this is data about
minors, including SEN status). For the demo, either (a) hand-collect a small
consented sample and say so explicitly in the pitch, or (b) keep this
synthetic and disclose it as illustrative.

Retrieval here is naive keyword overlap — swap for a real embedding store
(e.g. a vector DB) once you have a real corpus; the function signature is
the MCP tool contract, keep it stable.
"""
from __future__ import annotations

from ..schema import ChildProfile, SchoolFitEvidence
from .sen_support import get_school

# SYNTHETIC PLACEHOLDER DATA — see module docstring.
_EXPERIENCES: list[dict] = [
    {
        "school_id": "riverside_ps",
        "tags": ["autism", "sensory", "routine"],
        "text": "(synthetic) A parent of an autistic child described the quiet room as genuinely used, not just listed on paper — teacher gave advance notice of schedule changes.",
    },
    {
        "school_id": "maple_grove_ps",
        "tags": ["autism", "sensory", "routine", "visual schedule"],
        "text": "(synthetic) A parent noted the visual-schedule system helped their child adjust in the first term; noise-reduced classroom had to be requested explicitly, wasn't offered by default.",
    },
    {
        "school_id": "hillcrest_ps",
        "tags": ["dyslexia"],
        "text": "(synthetic) A parent felt general inclusive-classroom support was fine for mild needs but wouldn't have been enough for anything more involved.",
    },
    {
        "school_id": "brightpath_ps",
        "tags": ["social skills", "autism", "transitions"],
        "text": "(synthetic) A parent said the weekly social-skills group and buddy system for transitions made a real difference for their child's first year.",
    },
]


def community_tool(profile: ChildProfile, school_id: str) -> SchoolFitEvidence:
    school = get_school(school_id)
    if school is None:
        raise ValueError(f"Unknown school_id: {school_id}")

    query_tags = {t.lower() for t in (profile.sen_conditions + profile.sensory_preferences)}
    matches = [
        e
        for e in _EXPERIENCES
        if e["school_id"] == school_id and (query_tags & {t.lower() for t in e["tags"]})
    ]

    if not matches:
        return SchoolFitEvidence(
            school_id=school_id,
            source="community",
            summary=f"{school['name']}: no matching anonymised parent experiences on file yet for this need profile.",
            concern="Community-experience corpus is currently synthetic/sparse — treat as illustrative only.",
            score_0_to_1=0.5,
            citation="Synthetic placeholder dataset — needs a real, consented corpus before production use.",
        )

    summary = " / ".join(m["text"] for m in matches[:2])
    return SchoolFitEvidence(
        school_id=school_id,
        source="community",
        summary=f"{school['name']}: {summary}",
        concern="Illustrative synthetic data — not real parent testimony yet.",
        score_0_to_1=0.7,
        citation="Synthetic placeholder dataset — replace with a real, consented, anonymised corpus.",
    )
