"""Evidence comparison and follow-up questions, with no ranking or score."""
from __future__ import annotations

from .comparison_schema import (
    Assessment, CatalogueResponse, CatalogueSchool, CatalogueTopic, ComparisonCell,
    ComparisonRequest, ComparisonResponse, ComparisonRow, Evidence, FollowUpQuestion,
    Observation, Outcome, Requirement, _seed_schools,
)

NOTICE = (
    "All schools and seed snippets are fictional demo data, not verified school facts. "
    "Evidence you enter is recorded by parent, not independently verified. "
    "Demo snippets and parent experiences provide context only and cannot satisfy requirements. "
    "This comparison does not rank schools or estimate personal admission odds."
)
LIVE_NOTICE = (
    "Live web research was retrieved for these school names through OpenRouter. "
    "Sources and summaries are research leads, not independently verified facts; "
    "confirm important arrangements with the school. Parent-entered evidence is "
    "also recorded by parent, not independently verified. This comparison does "
    "not rank schools or estimate personal admission odds."
)
_TOPICS = [
    CatalogueTopic(
        id="quiet_space", label="Quiet space",
        description="Access to a quiet space and support during sensory breaks.",
        question="What quiet space can my child use, when is it available, and who helps them access it?",
    ),
    CatalogueTopic(
        id="learning_support", label="Learning support",
        description="Specific learning support, eligibility and arrangements.",
        question="What learning support can my child access, how often, and what are the eligibility and waiting arrangements?",
    ),
    CatalogueTopic(
        id="student_care", label="Student care",
        description="After-school care availability, hours and support.",
        question="Is a student-care place available, what are its hours, and how would my child's needs be supported?",
    ),
    CatalogueTopic(
        id="commute", label="Commute",
        description="Measured door-to-door travel time against your maximum minutes.",
        question="How long is a measured door-to-door journey at the usual school travel time, including waiting?",
    ),
    CatalogueTopic(
        id="workload", label="Workload",
        description="Typical homework demands and available adjustments.",
        question="What is the typical daily homework load, and what adjustments are available when my child needs them?",
    ),
    CatalogueTopic(
        id="social_inclusion", label="Social inclusion",
        description="Concrete arrangements for participation, friendships and concerns.",
        question="How will my child be supported to join activities and build friendships, and who handles exclusion concerns?",
    ),
    CatalogueTopic(
        id="cca", label="Co-curricular activities",
        description="Activity availability, entry arrangements and participation support.",
        question="Is the activity my child wants available, and what are the entry requirements, schedule and participation supports?",
    ),
    CatalogueTopic(
        id="custom", label="Other requirement",
        description="A specific requirement described by your family.",
        question="Can you meet the requirement described below, and what arrangements and limitations should we confirm?",
    ),
]
_TOPIC_BY_ID = {topic.id: topic for topic in _TOPICS}
_DIRECT_SOURCES = {"school_response", "published_information", "family_observation"}


def _school(request: ComparisonRequest, school_id: str) -> CatalogueSchool:
    if request.school_names is not None:
        index = request.school_ids.index(school_id)
        return CatalogueSchool(school_id=school_id, school_name=request.school_names[index], is_demo=False)
    return CatalogueSchool(school_id=school_id, school_name=_seed_schools()[school_id]["name"])


def get_catalogue() -> CatalogueResponse:
    return CatalogueResponse(
        schools=[CatalogueSchool(school_id=school_id, school_name=_seed_schools()[school_id]["name"])
                 for school_id in _seed_schools()],
        topics=[topic.model_copy() for topic in _TOPICS], notice=NOTICE,
    )


def _demo_evidence(school_id: str, requirement: Requirement) -> list[Evidence]:
    seed = _seed_schools()[school_id]
    if requirement.topic in {"quiet_space", "learning_support"}:
        snippet = seed.get("sen_support", {}).get("notes", "")
    elif requirement.topic == "cca":
        snippet = ", ".join(seed.get("cca", []))
    else:
        return []
    if not snippet:
        return []
    return [Evidence(
        id=f"demo:{school_id}:{requirement.topic}", source_type="demo",
        source_label="Fictional demo seed — not verified; context only",
        source_url=None, observed_on=None, summary=f"Fictional example: {snippet}",
        outcome="unclear", commute_minutes=None, is_demo=True,
    )]


def _outcome(observation: Observation, requirement: Requirement) -> Outcome:
    if requirement.topic != "commute":
        return observation.outcome
    if observation.commute_minutes is None:
        return "unclear"
    return "supports" if observation.commute_minutes <= requirement.max_minutes else "does_not_support"


def _cell(
    request: ComparisonRequest,
    requirement: Requirement,
    school_id: str,
    live_evidence: dict[tuple[str, str], list[Evidence]] | None = None,
) -> ComparisonCell:
    evidence = []
    direct_outcomes = set()
    for observation in request.observations:
        if observation.school_id != school_id or observation.requirement_id != requirement.id:
            continue
        outcome = _outcome(observation, requirement)
        evidence.append(Evidence(
            id=observation.id, source_type=observation.source_type,
            source_label=f"Recorded by parent, not independently verified — {observation.source_label}",
            source_url=observation.source_url, observed_on=observation.observed_on,
            summary=observation.summary, outcome=outcome,
            commute_minutes=observation.commute_minutes, is_demo=False,
        ))
        if observation.source_type in _DIRECT_SOURCES:
            direct_outcomes.add(outcome)
    if live_evidence is not None:
        live_sources = live_evidence.get((school_id, requirement.id), [])
        evidence.extend(live_sources)
        direct_outcomes.update(
            source.outcome for source in live_sources
            if source.source_type in _DIRECT_SOURCES
        )
    else:
        evidence.extend(_demo_evidence(school_id, requirement))

    if {"supports", "does_not_support"} <= direct_outcomes:
        status = "conflicting"
        explanation = "Recorded direct sources both support and do not support this requirement; clarify the disagreement. No source is silently preferred by date."
    elif "does_not_support" in direct_outcomes:
        status = "not_met"
        explanation = "Recorded direct evidence indicates this requirement is not met. Ask about alternatives or adjustments."
    elif "supports" in direct_outcomes:
        status = "supported"
        explanation = "Recorded direct evidence supports this requirement."
    else:
        status = "unknown"
        explanation = "There is no conclusive direct evidence for this requirement. Demo snippets and parent experiences are context only."
    if requirement.topic == "commute":
        explanation += (
            f" Measured journeys of {requirement.max_minutes:g} minutes or less support the limit; "
            "longer journeys do not. A missing measurement is unknown, regardless of the entered outcome."
        )
    explanation += (
        " Live research is a source lead to verify with the school."
        if live_evidence is not None
        else " Parent-entered evidence is recorded by parent, not independently verified."
    )
    if live_evidence is not None and not evidence:
        explanation = "Live research did not find a sufficiently specific source for this requirement. Ask the school directly."
    return ComparisonCell(school_id=school_id, status=status, explanation=explanation, evidence=evidence)


def _assessment(school_id: str, school_index: int, rows: list[ComparisonRow]) -> Assessment:
    statuses = [row.cells[school_index].status for row in rows if row.requirement.priority == "must_have"]
    supported = statuses.count("supported")
    if not statuses:
        state = "preferences_only"
        summary = "only preferences were supplied; no must-have requirements were assessed."
    elif "not_met" in statuses:
        state = "unmet_requirement"
        summary = "at least one must-have requirement is not met. Preferences cannot compensate for an unmet must-have."
    elif any(status in {"unknown", "conflicting"} for status in statuses):
        state = "needs_confirmation"
        summary = "at least one must-have requirement needs confirmation or clarification."
    else:
        state = "requirements_supported"
        summary = "all stated must-have requirements are supported by recorded direct evidence."
    return Assessment(
        school_id=school_id, state=state,
        summary=f"Based on the information you recorded, {summary} This evidence has not been independently verified.",
        supported_required=supported, total_required=len(statuses),
    )


def _questions(rows: list[ComparisonRow]) -> list[FollowUpQuestion]:
    questions = []
    for row in sorted(rows, key=lambda row: row.requirement.priority != "must_have"):
        requirement = row.requirement
        for cell in row.cells:
            if cell.status == "supported":
                continue
            question = _TOPIC_BY_ID[requirement.topic].question
            if requirement.topic == "commute":
                question += f" Can the journey be completed within {requirement.max_minutes:g} minutes? Please record the measured minutes and date."
            if cell.status == "conflicting":
                question = "Please clarify the conflicting recorded information and the circumstances behind each account. " + question
                reason = "Direct evidence conflicts; clarification is needed before treating this requirement as supported."
            elif cell.status == "not_met":
                question = "What alternatives or adjustments could meet this requirement, and when would they be available? " + question
                reason = "Recorded direct evidence indicates this requirement is not met; ask about practical alternatives."
            else:
                question = "Please confirm with a specific response or observation. " + question
                reason = "Direct evidence is missing or unclear; demo snippets and parent experiences cannot resolve the requirement."
            if requirement.details:
                question += f" Our specific requirement: {requirement.details}"
            questions.append(FollowUpQuestion(
                id=f"question:{cell.school_id}:{requirement.id}", school_id=cell.school_id,
                requirement_id=requirement.id, priority=requirement.priority,
                question=question, reason=reason,
            ))
    return questions


def compare_schools(
    request: ComparisonRequest,
    live_evidence: dict[tuple[str, str], list[Evidence]] | None = None,
) -> ComparisonResponse:
    rows = [ComparisonRow(
        requirement=requirement, label=_TOPIC_BY_ID[requirement.topic].label,
        cells=[_cell(request, requirement, school_id, live_evidence) for school_id in request.school_ids],
    ) for requirement in request.requirements]
    return ComparisonResponse(
        notice=LIVE_NOTICE if live_evidence is not None else NOTICE, context=request.context,
        schools=[_school(request, school_id) for school_id in request.school_ids], rows=rows,
        assessments=[_assessment(school_id, index, rows) for index, school_id in enumerate(request.school_ids)],
        questions=_questions(rows),
    )
