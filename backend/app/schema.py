"""Structured types shared across the graph.

Everything downstream (tools, synthesis) reads/writes these — keeping them
typed is what let us catch profile-extraction bugs before they hit an LLM
call three nodes later.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChildProfile(BaseModel):
    """Structured extraction target for the parent's free-text description.

    The profile-extraction node's only job is to fill this in from natural
    language. Every field the synthesis node needs later must be named here
    first — resist the urge to smuggle extra info through free-text notes.
    """

    home_postal_district: Optional[str] = Field(
        None, description="Singapore postal district or postal code prefix, e.g. '52' or '520123'"
    )
    home_address_text: Optional[str] = Field(
        None, description="Raw address or landmark as the parent described it, for geocoding"
    )
    registration_phase: Optional[
        Literal["1", "2A1", "2A2", "2B", "2C", "2C_SUPP", "3", "unknown"]
    ] = Field(None, description="MOE P1 registration phase the family qualifies for")

    sen_conditions: list[str] = Field(
        default_factory=list,
        description="Named conditions/needs the parent stated, e.g. ['autism', 'sensory sensitivity']",
    )
    sensory_preferences: list[str] = Field(
        default_factory=list,
        description="Sensory needs, e.g. ['noise-sensitive', 'needs predictable routine']",
    )
    social_behaviour_notes: Optional[str] = Field(
        None, description="Free-text summary of social/behavioural traits the parent described"
    )

    cca_interests: list[str] = Field(default_factory=list)
    alumni_schools: list[str] = Field(
        default_factory=list, description="Schools where a parent/sibling is an alumnus, if stated"
    )

    max_commute_minutes: Optional[int] = None

    # Carried through the graph, not extracted from text.
    raw_input: str = ""


class SchoolFitEvidence(BaseModel):
    """One sub-agent's findings about one school, before synthesis."""

    school_id: str
    source: Literal["sen_support", "commute", "admission_odds", "community"]
    summary: str
    concern: Optional[str] = None
    score_0_to_1: float = Field(ge=0.0, le=1.0)
    citation: Optional[str] = None


class SchoolFitResult(BaseModel):
    """Final per-school output shown to the parent."""

    school_id: str
    school_name: str
    fit_summary: str
    concerns: list[str] = Field(default_factory=list)
    distance_km: Optional[float] = None
    commute_minutes: Optional[int] = None
    admission_odds_pct: Optional[float] = None
    evidence: list[SchoolFitEvidence] = Field(default_factory=list)
