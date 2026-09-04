"""Smoke test — runs the full graph end-to-end with MODEL_PROVIDER=fake
(no API key needed). Run with: pytest backend/tests/test_graph.py -q
"""
import os

os.environ.setdefault("MODEL_PROVIDER", "fake")

from app.graph import run  # noqa: E402


def test_graph_runs_and_returns_ranked_schools():
    results = run(
        "My son is autistic, sensitive to noise and needs predictable routines. "
        "We're in Phase 2C. Which nearby schools might suit him?"
    )
    assert len(results) > 0
    assert all(r.fit_summary for r in results)
    # Ranked: first result's combined evidence score should be >= last's.
    first_score = sum(e.score_0_to_1 for e in results[0].evidence) / len(results[0].evidence)
    last_score = sum(e.score_0_to_1 for e in results[-1].evidence) / len(results[-1].evidence)
    assert first_score >= last_score


def test_profile_extraction_picks_up_stated_needs():
    from app.extract import extract_profile

    profile = extract_profile("My daughter has ADHD and loves climbing and robotics.")
    assert "adhd" in profile.sen_conditions
    assert "climbing" in profile.cca_interests
