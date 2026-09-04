"""Admission-odds tool — Bayesian (Beta-Binomial), not a trained neural net.

Why: with only a handful of years of phase-level vacancy/applicant counts per
school, there isn't remotely enough data to train a neural net without
overfitting. A Beta-Binomial model gives calibrated, explainable odds from
just a few data points, and updates cleanly as new phase results come in
(posterior update, no retraining pipeline needed).

odds ≈ vacancies / applicants when oversubscribed, else ~1.0 (undersubscribed
phases aren't balloted). We treat each historical year as one Beta-Binomial
observation and blend a weak uniform prior with the observed fill pattern.
"""
from __future__ import annotations

from ..schema import ChildProfile, SchoolFitEvidence
from .sen_support import get_school

# Weak prior: Beta(2, 2) — mildly favors "uncertain, could go either way"
# until real data pulls it one direction. Tune once you have more schools.
_PRIOR_ALPHA = 2.0
_PRIOR_BETA = 2.0


def estimate_odds(school: dict, phase: str) -> tuple[float, int]:
    """Returns (odds_pct, years_of_data)."""
    history = school.get("historical_admissions", {}).get(phase, {})
    if not history:
        return 50.0, 0  # no data — flag as unknown, don't fabricate confidence

    alpha, beta = _PRIOR_ALPHA, _PRIOR_BETA
    for _year, rec in history.items():
        vacancies, applicants = rec["vacancies"], rec["applicants"]
        if applicants <= 0:
            continue
        if applicants <= vacancies:
            # Undersubscribed: effectively everyone who applies gets in.
            alpha += vacancies
        else:
            # Oversubscribed: treat as `vacancies` successes out of
            # `applicants` trials for that year.
            alpha += vacancies
            beta += applicants - vacancies

    posterior_mean = alpha / (alpha + beta)
    return round(posterior_mean * 100, 1), len(history)


def admission_odds_tool(profile: ChildProfile, school_id: str) -> SchoolFitEvidence:
    school = get_school(school_id)
    if school is None:
        raise ValueError(f"Unknown school_id: {school_id}")

    phase = profile.registration_phase or "2C"
    odds_pct, n_years = estimate_odds(school, phase)

    concern = None
    if n_years == 0:
        concern = f"No historical data for Phase {phase} at this school — odds shown are an uninformed prior, verify manually."
    elif odds_pct < 40:
        concern = f"Historically competitive for Phase {phase} — consider it a stretch choice, not a safe one."

    return SchoolFitEvidence(
        school_id=school_id,
        source="admission_odds",
        summary=f"{school['name']}: ~{odds_pct}% estimated odds for Phase {phase}, based on {n_years} year(s) of MOE-published vacancy/applicant data.",
        concern=concern,
        score_0_to_1=round(odds_pct / 100, 2),
        citation="Bayesian (Beta-Binomial) posterior over MOE P1 registration exercise historical results — replace seed data with real published figures.",
    )
