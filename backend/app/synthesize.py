"""Combine per-tool evidence into the parent-facing explanation.

This node is the actual product differentiator (your solution doc's "explain
why, don't just rank" requirement) — it's the one place we always want a
strong model, even if profile extraction runs on the cheap/fake path.
"""
from __future__ import annotations

from .llm import get_chat_model, is_fake
from .schema import SchoolFitEvidence, SchoolFitResult
from .tools import get_school

_SYSTEM_PROMPT = """You explain, in 2-3 plain-language sentences, why a specific
Singapore primary school may or may not suit a specific child. You are given
structured evidence about SEN support, commute, admission odds, and community
experience. Be concrete and specific to the evidence given -- name the actual
support programme or concern, don't write generic praise. If the evidence is
weak or the school is a poor fit, say so plainly; do not oversell every
school. Do not invent facts not present in the evidence."""


def _template_explanation(school_name: str, evidence: list[SchoolFitEvidence]) -> str:
    """Deterministic fallback used when MODEL_PROVIDER=fake — no LLM call."""
    by_source = {e.source: e for e in evidence}
    parts = []
    if "sen_support" in by_source:
        parts.append(by_source["sen_support"].summary)
    if "commute" in by_source:
        parts.append(by_source["commute"].summary)
    if "admission_odds" in by_source:
        parts.append(by_source["admission_odds"].summary)
    return " ".join(parts) if parts else f"No evidence gathered yet for {school_name}."


def _llm_explanation(school_name: str, evidence: list[SchoolFitEvidence]) -> str:
    model = get_chat_model(temperature=0.2)
    evidence_text = "\n".join(f"- [{e.source}] {e.summary} (concern: {e.concern or 'none'})" for e in evidence)
    resp = model.invoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"School: {school_name}\n\nEvidence:\n{evidence_text}\n\nWrite the explanation now.",
            },
        ]
    )
    return resp.content if hasattr(resp, "content") else str(resp)


def synthesize_school(school_id: str, evidence: list[SchoolFitEvidence]) -> SchoolFitResult:
    school = get_school(school_id)
    school_name = school["name"] if school else school_id

    fit_summary = (
        _template_explanation(school_name, evidence) if is_fake() else _llm_explanation(school_name, evidence)
    )
    concerns = [e.concern for e in evidence if e.concern]

    by_source = {e.source: e for e in evidence}
    commute_ev = by_source.get("commute")
    odds_ev = by_source.get("admission_odds")

    return SchoolFitResult(
        school_id=school_id,
        school_name=school_name,
        fit_summary=fit_summary,
        concerns=concerns,
        distance_km=None,  # populate from commute_ev if you extend SchoolFitEvidence with raw fields
        commute_minutes=None,
        admission_odds_pct=(odds_ev.score_0_to_1 * 100) if odds_ev else None,
        evidence=evidence,
    )


def rank_results(results: list[SchoolFitResult]) -> list[SchoolFitResult]:
    def combined_score(r: SchoolFitResult) -> float:
        if not r.evidence:
            return 0.0
        return sum(e.score_0_to_1 for e in r.evidence) / len(r.evidence)

    return sorted(results, key=combined_score, reverse=True)
