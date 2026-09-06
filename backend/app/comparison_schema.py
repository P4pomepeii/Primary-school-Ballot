"""Strict, JSON-compatible contracts for the evidence-based comparison API."""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, TypeAdapter,
    field_validator, model_validator,
)

Topic = Literal[
    "quiet_space", "learning_support", "student_care", "commute", "workload",
    "social_inclusion", "cca", "custom",
]
Priority = Literal["must_have", "preference"]
ObservationSource = Literal[
    "school_response", "published_information", "parent_experience", "family_observation",
]
Outcome = Literal["supports", "does_not_support", "unclear"]
Status = Literal["supported", "not_met", "unknown", "conflicting"]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Minutes = Annotated[float, Field(ge=1, le=300, allow_inf_nan=False)]
SINGAPORE = ZoneInfo("Asia/Singapore")
_HTTP_URL = TypeAdapter(HttpUrl)


@lru_cache(maxsize=1)
def _seed_schools() -> dict[str, dict]:
    data = json.loads((Path(__file__).parent / "data" / "schools.json").read_text())
    return {school["id"]: school for school in data["schools"]}


class ComparisonModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def trim_strings(cls, value):
        # Literal fields also need trimming; str_strip_whitespace covers strings only.
        return value.strip() if isinstance(value, str) else value


class Requirement(ComparisonModel):
    id: Identifier
    topic: Topic
    priority: Priority
    details: str = Field(max_length=500)
    max_minutes: Annotated[float, Field(ge=1, le=180, allow_inf_nan=False)] | None

    @model_validator(mode="after")
    def validate_topic_fields(self):
        if self.topic == "commute" and self.max_minutes is None:
            raise ValueError("Commute requirements need max_minutes between 1 and 180.")
        if self.topic != "commute" and self.max_minutes is not None:
            raise ValueError("Only commute requirements may have max_minutes.")
        if self.topic == "custom" and not self.details:
            raise ValueError("Custom requirements need details.")
        return self


class Observation(ComparisonModel):
    id: Identifier
    school_id: Identifier
    requirement_id: Identifier
    source_type: ObservationSource
    source_label: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(max_length=2048)
    observed_on: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", max_length=10)
    summary: str = Field(min_length=1, max_length=2000)
    outcome: Outcome
    commute_minutes: Minutes | None

    @field_validator("observed_on")
    @classmethod
    def validate_date(cls, value: str) -> str:
        try:
            observed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("observed_on must be a valid YYYY-MM-DD date.") from None
        if observed > datetime.now(SINGAPORE).date():
            raise ValueError("observed_on cannot be in the future in Singapore.")
        return value

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is not None:
            if any(character.isspace() for character in value):
                raise ValueError("source_url must be a valid HTTP or HTTPS URL.")
            try:
                _HTTP_URL.validate_python(value)
            except ValueError:
                raise ValueError("source_url must be a valid HTTP or HTTPS URL.") from None
        return value

    @model_validator(mode="after")
    def validate_published_source(self):
        if self.source_type == "published_information" and self.source_url is None:
            raise ValueError("Published information requires a source_url.")
        return self


class ComparisonRequest(ComparisonModel):
    school_ids: list[Identifier] = Field(min_length=2, max_length=2)
    context: str = Field(max_length=3000)
    requirements: list[Requirement] = Field(min_length=1, max_length=8)
    observations: list[Observation] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_references(self):
        if len(set(self.school_ids)) != 2:
            raise ValueError("Select two distinct schools.")
        if any(school_id not in _seed_schools() for school_id in self.school_ids):
            raise ValueError("Select schools from the school catalogue.")
        requirements = {requirement.id: requirement for requirement in self.requirements}
        if len(requirements) != len(self.requirements):
            raise ValueError("Requirement ids must be unique.")
        if len({requirement.topic for requirement in self.requirements}) != len(self.requirements):
            raise ValueError("Requirement topics must be unique.")
        if len({observation.id for observation in self.observations}) != len(self.observations):
            raise ValueError("Observation ids must be unique.")
        for observation in self.observations:
            if observation.school_id not in self.school_ids:
                raise ValueError("Observations must reference a selected school.")
            if observation.requirement_id not in requirements:
                raise ValueError("Observations must reference an included requirement.")
            if (observation.commute_minutes is not None
                    and requirements[observation.requirement_id].topic != "commute"):
                raise ValueError("Only commute observations may have commute_minutes.")
        return self


class CatalogueSchool(ComparisonModel):
    school_id: str
    school_name: str
    is_demo: Literal[True] = True


class CatalogueTopic(ComparisonModel):
    id: Topic
    label: str
    description: str
    question: str


class CatalogueResponse(ComparisonModel):
    schools: list[CatalogueSchool]
    topics: list[CatalogueTopic]
    notice: str


class Evidence(ComparisonModel):
    id: str
    source_type: Literal["demo"] | ObservationSource
    source_label: str
    source_url: str | None
    observed_on: str | None
    summary: str
    outcome: Outcome
    commute_minutes: Minutes | None
    is_demo: bool


class ComparisonCell(ComparisonModel):
    school_id: str
    status: Status
    explanation: str
    evidence: list[Evidence]


class ComparisonRow(ComparisonModel):
    requirement: Requirement
    label: str
    cells: list[ComparisonCell]


class Assessment(ComparisonModel):
    school_id: str
    state: Literal[
        "needs_confirmation", "unmet_requirement", "requirements_supported", "preferences_only",
    ]
    summary: str
    supported_required: int
    total_required: int


class FollowUpQuestion(ComparisonModel):
    id: str
    school_id: str
    requirement_id: str
    priority: Priority
    question: str
    reason: str


class ComparisonResponse(ComparisonModel):
    notice: str
    context: str
    schools: list[CatalogueSchool]
    rows: list[ComparisonRow]
    assessments: list[Assessment]
    questions: list[FollowUpQuestion]
