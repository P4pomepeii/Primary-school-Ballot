"""Comparison decisions and API boundaries, with no external services."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import comparison_schema
from app.compare import compare_schools, get_catalogue
from app.comparison_schema import ComparisonRequest, ComparisonResponse, Evidence
from app.live_research import _findings
from app.server import app

FIRST, SECOND = "riverside_ps", "hillcrest_ps"
TOPICS = ["quiet_space", "learning_support", "student_care", "commute", "workload", "social_inclusion", "cca", "custom"]


def requirement(topic="quiet_space", **changes):
    return {
        "id": topic, "topic": topic, "priority": "must_have",
        "details": "A specific arrangement" if topic == "custom" else "",
        "max_minutes": 30 if topic == "commute" else None,
        **changes,
    }


def observation(**changes):
    return {
        "id": "note-1", "school_id": FIRST, "requirement_id": "quiet_space",
        "source_type": "school_response", "source_label": "School visit notes",
        "source_url": None, "observed_on": "2020-01-01", "summary": "We recorded the arrangements.",
        "outcome": "supports", "commute_minutes": None, **changes,
    }


def payload(requirements=None, observations=None, **changes):
    return {
        "school_ids": [FIRST, SECOND], "context": "Our family's priorities",
        "requirements": requirements if requirements is not None else [requirement()],
        "observations": observations if observations is not None else [], **changes,
    }


def compare(requirements=None, observations=None, **changes):
    return compare_schools(ComparisonRequest.model_validate(payload(requirements, observations, **changes)))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_demo_never_resolves_any_topic_or_fabricates_dates():
    result = compare([requirement(topic) for topic in TOPICS])
    assert all(assessment.state == "needs_confirmation" for assessment in result.assessments)
    assert all(assessment.supported_required == 0 for assessment in result.assessments)
    assert len(result.questions) == 16
    for row in result.rows:
        for cell in row.cells:
            assert cell.status == "unknown"
            assert bool(cell.evidence) == (row.requirement.topic in {"quiet_space", "learning_support", "cca"})
            for evidence in cell.evidence:
                assert evidence.source_type == "demo" and evidence.is_demo is True
                assert "fictional" in evidence.source_label.lower()
                assert evidence.observed_on is None and evidence.source_url is None
                assert evidence.outcome == "unclear" and evidence.commute_minutes is None


@pytest.mark.parametrize("source_type", ["school_response", "published_information", "family_observation"])
@pytest.mark.parametrize("outcome,status", [("supports", "supported"), ("does_not_support", "not_met"), ("unclear", "unknown")])
def test_only_conclusive_direct_evidence_resolves(source_type, outcome, status):
    result = compare(observations=[observation(
        source_type=source_type, outcome=outcome,
        source_url="https://example.com/support" if source_type == "published_information" else None,
    )])
    assert result.rows[0].cells[0].status == status
    assert result.rows[0].cells[1].status == "unknown"
    evidence = result.rows[0].cells[0].evidence[0]
    assert "recorded by parent, not independently verified" in evidence.source_label.lower()
    assert evidence.is_demo is False
    assert evidence.observed_on == "2020-01-01"  # No arbitrary staleness cutoff.


@pytest.mark.parametrize("outcome", ["supports", "does_not_support", "unclear"])
def test_parent_experience_cannot_resolve_or_override_direct_evidence(outcome):
    anecdote = observation(source_type="parent_experience", outcome=outcome)
    result = compare(observations=[anecdote])
    assert result.rows[0].cells[0].status == "unknown"
    assert result.rows[0].cells[0].evidence[0].source_type == "parent_experience"
    direct = observation(id="direct", outcome="supports")
    assert compare(observations=[anecdote, direct]).rows[0].cells[0].status == "supported"


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_direct_sources_are_not_resolved_by_newest(reverse):
    notes = [
        observation(id="older", outcome="supports", observed_on="2000-01-01"),
        observation(id="newer", outcome="does_not_support", observed_on="2020-01-01"),
    ]
    result = compare([requirement(details="Access during noisy assemblies")], list(reversed(notes)) if reverse else notes)
    assert result.rows[0].cells[0].status == "conflicting"
    assert result.assessments[0].state == "needs_confirmation"
    question = result.questions[0]
    assert "clarif" in question.question.lower() and "conflict" in question.question.lower()
    assert "Access during noisy assemblies" in question.question


@pytest.mark.parametrize("missing_status", ["unknown", "conflicting"])
def test_unmet_must_have_cannot_be_compensated_by_preferences_or_unknowns(missing_status):
    requirements = [requirement("cca", priority="preference"), requirement(), requirement("learning_support")]
    notes = [observation(requirement_id="quiet_space", outcome="does_not_support"),
             observation(id="activity", requirement_id="cca", outcome="supports")]
    if missing_status == "conflicting":
        notes.extend([observation(id="learning-yes", requirement_id="learning_support"),
                      observation(id="learning-no", requirement_id="learning_support", outcome="does_not_support")])
    result = compare(requirements, notes)
    assessment = result.assessments[0]
    assert assessment.state == "unmet_requirement"
    assert assessment.supported_required == 0 and assessment.total_required == 2
    assert "cannot compensate" in assessment.summary
    assert "alternatives" in result.questions[0].question
    priorities = [question.priority for question in result.questions]
    assert priorities == sorted(priorities, key=lambda value: value != "must_have")


def test_supported_requirements_and_preferences_only_are_distinct():
    requirements = [requirement(), requirement("cca", priority="preference")]
    result = compare(requirements, [observation()])
    assert result.assessments[0].state == "requirements_supported"
    assert result.assessments[0].supported_required == result.assessments[0].total_required == 1
    assert all(question.requirement_id != "quiet_space" or question.school_id != FIRST for question in result.questions)
    preference_result = compare([requirement(priority="preference")], [observation(outcome="does_not_support")])
    for assessment in preference_result.assessments:
        assert assessment.state == "preferences_only" and assessment.total_required == 0
    for assessment in result.assessments + preference_result.assessments:
        assert assessment.summary.startswith("Based on the information you recorded")


@pytest.mark.parametrize("minutes,outcome,status,effective", [
    (29.9, "does_not_support", "supported", "supports"),
    (30, "does_not_support", "supported", "supports"),
    (30.1, "supports", "not_met", "does_not_support"),
    (1, "unclear", "supported", "supports"),
    (300, "supports", "not_met", "does_not_support"),
    (None, "supports", "unknown", "unclear"),
    (None, "does_not_support", "unknown", "unclear"),
])
def test_commute_uses_measured_minutes_not_entered_outcome(minutes, outcome, status, effective):
    result = compare([requirement("commute")], [observation(
        requirement_id="commute", commute_minutes=minutes, outcome=outcome,
    )])
    cell = result.rows[0].cells[0]
    assert cell.status == status and cell.evidence[0].outcome == effective
    assert cell.evidence[0].commute_minutes == minutes
    if status != "supported":
        assert "30 minutes" in result.questions[0].question
        assert "measured minutes and date" in result.questions[0].question


def test_commute_conflicting_measurements_and_anecdotal_measurements():
    notes = [observation(id="short", requirement_id="commute", commute_minutes=20),
             observation(id="long", requirement_id="commute", commute_minutes=40)]
    assert compare([requirement("commute")], notes).rows[0].cells[0].status == "conflicting"
    for note in notes:
        note["source_type"] = "parent_experience"
    assert compare([requirement("commute")], notes).rows[0].cells[0].status == "unknown"


def test_comparison_keeps_school_and_requirement_order():
    result = compare([requirement("cca"), requirement()], school_ids=[SECOND, FIRST])
    assert [school.school_id for school in result.schools] == [SECOND, FIRST]
    assert [assessment.school_id for assessment in result.assessments] == [SECOND, FIRST]
    assert [row.requirement.topic for row in result.rows] == ["cca", "quiet_space"]
    assert all([cell.school_id for cell in row.cells] == [SECOND, FIRST] for row in result.rows)
    assert [question.school_id for question in result.questions] == [SECOND, FIRST, SECOND, FIRST]
    assert len({question.id for question in result.questions}) == len(result.questions)


@pytest.mark.parametrize("school_ids", [[FIRST], [FIRST, SECOND, "maple_grove_ps"], [FIRST, FIRST], [FIRST, "unknown"], [FIRST, f" {FIRST} "]])
def test_requires_two_distinct_known_schools(school_ids):
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(school_ids=school_ids))


@pytest.mark.parametrize("requirements", [
    [], [requirement()] * 9,
    [requirement(), requirement("cca", id="quiet_space")],
    [requirement(), requirement(id="different")],
    [requirement("custom", details="  ")],
    [requirement("commute", max_minutes=None)],
    [requirement("commute", max_minutes=0)],
    [requirement("commute", max_minutes=181)],
    [requirement("commute", max_minutes=True)],
    [requirement("commute", max_minutes="30")],
    [requirement("commute", max_minutes=float("nan"))],
    [requirement(max_minutes=30)],
    [requirement(topic="teacher_quality")],
    [requirement(priority="high")],
    [requirement(id=" ")], [requirement(id="x" * 65)],
    [requirement(details="x" * 501)], [requirement(secret="personal")],
])
def test_invalid_requirements_are_rejected(requirements):
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(requirements=requirements))


@pytest.mark.parametrize("changes", [
    {"school_id": "maple_grove_ps"}, {"school_id": "unknown"}, {"requirement_id": "not-in-request"},
    {"observed_on": "9999-01-01"}, {"observed_on": "2020-02-30"},
    {"observed_on": "2020-1-1"}, {"observed_on": "2020-01-01T00:00:00Z"},
    {"observed_on": 20200101},
    {"source_url": "javascript:alert(1)"}, {"source_url": "ftp://example.com"},
    {"source_url": "/relative"}, {"source_url": "https://"},
    {"source_url": "https://exa\nmple.com"}, {"source_url": "https://example.com/" + "x" * 2048},
    {"source_type": "published_information", "source_url": None},
    {"commute_minutes": 20}, {"source_type": "demo"}, {"outcome": "likely"},
    {"summary": "  "}, {"summary": "x" * 2001}, {"source_label": " "},
    {"source_label": "x" * 201}, {"id": 123}, {"secret": "personal"},
])
def test_invalid_observations_are_rejected(changes):
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(observations=[observation(**changes)]))


@pytest.mark.parametrize("minutes", [-1, 0, 0.99, 300.01, 301, True, "20", float("inf"), float("nan")])
def test_invalid_commute_measurements_are_rejected(minutes):
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload([requirement("commute")], [observation(requirement_id="commute", commute_minutes=minutes)]))


def test_observation_count_and_unique_ids_are_enforced():
    notes = [observation(id=f"note-{index}") for index in range(101)]
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(observations=notes))
    assert len(ComparisonRequest.model_validate(payload(observations=notes[:100])).observations) == 100
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(observations=[observation(), observation()]))


@pytest.mark.parametrize("changes", [{"secret": "personal"}, {"context": "x" * 3001}, {"context": False}])
def test_top_level_extra_fields_and_invalid_context_are_rejected(changes):
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(**changes))


def test_dates_use_singapore_today_at_utc_day_boundary(monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(comparison_schema, "datetime", FrozenDatetime)
    ComparisonRequest.model_validate(payload(observations=[observation(observed_on="2026-01-02")]))
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(payload(observations=[observation(observed_on="2026-01-03")]))


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_input_strings_trim_and_http_urls_preserve_source(scheme):
    request = ComparisonRequest.model_validate(payload(
        [requirement(id=" quiet ", topic=" quiet_space ", priority=" must_have ", details=" Breaks after assembly ")],
        [observation(id=" note ", school_id=f" {FIRST} ", requirement_id=" quiet ",
                     source_type=" published_information ", source_label=" School page ",
                     source_url=f" {scheme}://example.com/support ", summary=" Notes ", outcome=" supports ")],
        school_ids=[f" {FIRST} ", SECOND], context=" Family context ",
    ))
    assert request.context == "Family context" and request.school_ids == [FIRST, SECOND]
    assert request.requirements[0].details == "Breaks after assembly"
    assert request.observations[0].id == "note" and request.observations[0].summary == "Notes"
    assert request.observations[0].source_url == f"{scheme}://example.com/support"
    assert compare_schools(request).rows[0].cells[0].status == "supported"


def test_api_catalogue_and_comparison_exact_contract_and_no_model_calls(client, monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("The comparison API must not invoke the graph or a model")

    monkeypatch.setattr("app.server.run", unexpected_call)
    monkeypatch.setattr("app.graph.get_graph", unexpected_call)
    monkeypatch.setattr("app.llm.get_chat_model", unexpected_call)
    catalogue = client.get("/schools")
    assert catalogue.status_code == 200 and catalogue.headers["cache-control"] == "no-store"
    data = catalogue.json()
    assert set(data) == {"schools", "topics", "notice"}
    assert data == get_catalogue().model_dump(mode="json")
    assert [topic["id"] for topic in data["topics"]] == TOPICS
    assert all(set(topic) == {"id", "label", "description", "question"} for topic in data["topics"])
    assert all(school["is_demo"] is True for school in data["schools"])
    assert "fictional" in data["notice"].lower()

    response = client.post("/compare", json=payload(observations=[observation(outcome="unclear")], school_ids=[SECOND, FIRST]))
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    result = response.json()
    assert set(result) == {"notice", "context", "schools", "rows", "assessments", "questions"}
    assert ComparisonResponse.model_validate(result).model_dump(mode="json") == result
    assert [school["school_id"] for school in result["schools"]] == [SECOND, FIRST]
    assert all(set(school) == {"school_id", "school_name", "is_demo"} for school in result["schools"])
    assert all(set(row) == {"requirement", "label", "cells"} for row in result["rows"])
    for row in result["rows"]:
        assert set(row["requirement"]) == {"id", "topic", "priority", "details", "max_minutes"}
        for cell in row["cells"]:
            assert set(cell) == {"school_id", "status", "explanation", "evidence"}
            for evidence in cell["evidence"]:
                assert set(evidence) == {"id", "source_type", "source_label", "source_url", "observed_on", "summary", "outcome", "commute_minutes", "is_demo"}
    assert all(set(assessment) == {"school_id", "state", "summary", "supported_required", "total_required"} for assessment in result["assessments"])
    assert all(set(question) == {"id", "school_id", "requirement_id", "priority", "question", "reason"} for question in result["questions"])


@pytest.mark.parametrize("invalid", [
    payload(school_ids=[FIRST, FIRST]),
    payload(school_ids=[FIRST, "PRIVATE_CHILD_DETAIL"]),
    payload(requirements=[requirement(topic="PRIVATE_CHILD_DETAIL")]),
    payload(observations=[observation(source_url="PRIVATE_CHILD_DETAIL")]),
    payload(observations=[observation(school_id="maple_grove_ps")]),
    payload(observations=[observation(observed_on="9999-01-01")]),
    payload(observations=[observation(summary="x" * 2001)]),
    payload(observations=[observation(PRIVATE_CHILD_DETAIL="PRIVATE_CHILD_DETAIL")]),
    payload(PRIVATE_CHILD_DETAIL="PRIVATE_CHILD_DETAIL"),
])
def test_api_validation_is_422_no_store_and_does_not_echo_input(client, invalid):
    invalid["context"] = "PRIVATE_CHILD_DETAIL"
    response = client.post("/compare", json=invalid)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert "PRIVATE_CHILD_DETAIL" not in response.text
    assert response.json()["detail"]
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


@pytest.mark.parametrize("field,limit", [("context", 3000), ("details", 500), ("summary", 2000), ("source_label", 200)])
def test_api_text_bounds_match_ui(client, field, limit):
    data = payload(observations=[observation()])
    target = {
        "context": data, "details": data["requirements"][0],
        "summary": data["observations"][0], "source_label": data["observations"][0],
    }[field]
    target[field] = "x" * limit
    assert client.post("/compare", json=data).status_code == 200
    target[field] += "x"
    response = client.post("/compare", json=data)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert any(error["loc"][-1] == field for error in response.json()["detail"])


@pytest.mark.parametrize("minutes,maximum,status", [(1, 1, "supported"), (300, 180, "not_met")])
def test_api_commute_boundaries_preserve_separate_requirement_limit(client, minutes, maximum, status):
    data = payload([requirement("commute", max_minutes=maximum)], [
        observation(requirement_id="commute", commute_minutes=minutes),
    ])
    response = client.post("/compare", json=data)
    assert response.status_code == 200
    cell = response.json()["rows"][0]["cells"][0]
    assert cell["status"] == status and cell["evidence"][0]["commute_minutes"] == minutes
    data["observations"][0]["commute_minutes"] = 0 if minutes == 1 else 301
    assert client.post("/compare", json=data).status_code == 422


def test_invalid_json_also_has_private_validation_response(client):
    response = client.post("/compare", content='{"context":"PRIVATE_CHILD_DETAIL",', headers={"content-type": "application/json"})
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert "PRIVATE_CHILD_DETAIL" not in response.text


def test_api_rejects_tomorrow(client):
    tomorrow = (datetime.now(comparison_schema.SINGAPORE).date() + timedelta(days=1)).isoformat()
    assert client.post("/compare", json=payload(observations=[observation(observed_on=tomorrow)])).status_code == 422


def test_invoke_full_graph_smoke_is_preserved(client, monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "fake")
    response = client.post("/invoke", json={"message": "My child has ADHD and enjoys robotics. We are in Phase 2C."})
    assert response.status_code == 200
    assert set(response.json()) == {"results"}
    assert response.json()["results"]
    assert all(result["fit_summary"] for result in response.json()["results"])
    assert client.get("/health").json() == {"status": "ok"}


def real_payload(**changes):
    return {
        "school_ids": ["school-1-tao-nan", "school-2-nanyang"],
        "school_names": ["Tao Nan School", "Nanyang Primary School"],
        "context": "We need a specific support arrangement.",
        "requirements": [requirement(id="quiet-space", details="A quiet space during the school day")],
        "observations": [],
        **changes,
    }


def test_real_school_names_skip_fictional_seed_evidence():
    request = ComparisonRequest.model_validate(real_payload())
    live = {(
        "school-1-tao-nan", "quiet-space",
    ): [Evidence(
        id="live:source", source_type="published_information", source_label="Live web research via OpenRouter — School page",
        source_url="https://example.com/tao-nan", observed_on="2026-09-06",
        summary="The source describes the relevant arrangement.", outcome="supports",
        commute_minutes=None, is_demo=False,
    )]}
    result = compare_schools(request, live_evidence=live)
    assert [school.school_name for school in result.schools] == ["Tao Nan School", "Nanyang Primary School"]
    assert all(school.is_demo is False for school in result.schools)
    assert result.rows[0].cells[0].status == "supported"
    assert result.rows[0].cells[1].status == "unknown"
    assert all(evidence.is_demo is False for row in result.rows for cell in row.cells for evidence in cell.evidence)
    assert "live web research" in result.notice.lower()


def test_real_school_api_uses_research_pass(client, monkeypatch):
    request = ComparisonRequest.model_validate(real_payload())
    evidence = Evidence(
        id="live:source", source_type="published_information", source_label="Live web research — School page",
        source_url="https://example.com/tao-nan", observed_on="2026-09-06",
        summary="The source describes the arrangement.", outcome="supports",
        commute_minutes=None, is_demo=False,
    )
    called = []

    def fake_research(received):
        called.append(received.school_names)
        return {("school-1-tao-nan", "quiet-space"): [evidence]}

    monkeypatch.setattr("app.server.research_schools", fake_research)
    response = client.post("/compare", json=real_payload())
    assert response.status_code == 200
    assert called == [["Tao Nan School", "Nanyang Primary School"]]
    assert response.json()["rows"][0]["cells"][0]["status"] == "supported"
    assert response.json()["rows"][0]["cells"][0]["evidence"][0]["source_url"] == "https://example.com/tao-nan"


def test_live_parser_accepts_provider_preamble_and_grouped_findings():
    request = ComparisonRequest.model_validate(real_payload())
    payload = {"choices": [{"message": {"content": """Research complete.
```json
[
  {"school_id":"school-1-tao-nan","requirement_id":"quiet-space","findings":[
    {"source_url":"https://example.com/tao-nan","excerpt":"A quiet space is described.","support":"supports"}
  ]}
]
```"""}}]}
    result = _findings(payload, request)
    assert result[("school-1-tao-nan", "quiet-space")][0].outcome == "supports"
    assert result[("school-1-tao-nan", "quiet-space")][0].source_url == "https://example.com/tao-nan"
