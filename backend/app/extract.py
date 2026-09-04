"""Turn the parent's free text into a ChildProfile.

Two paths:
  - fake/offline: keyword-matching extractor. Deliberately simple — good
    enough to exercise the rest of the graph without any API key.
  - real provider: LLM structured output via .with_structured_output(),
    same pattern as your training deck's Planning: Decomposition slide
    (`planner.invoke(...).steps` -> here it's `.invoke(...)` -> ChildProfile).
"""
from __future__ import annotations

import re

from .llm import get_chat_model, is_fake
from .schema import ChildProfile

_SEN_KEYWORDS = {
    "autism": ["autistic", "autism", "asd"],
    "adhd": ["adhd", "attention deficit"],
    "dyslexia": ["dyslexia", "dyslexic"],
}
_SENSORY_KEYWORDS = {
    "noise-sensitive": ["noise", "loud", "sound sensitive"],
    "needs predictable routine": ["routine", "predictable", "structure"],
}
_CCA_KEYWORDS = ["climbing", "swimming", "robotics", "art", "choir", "football", "chess", "coding", "orchestra"]

_SYSTEM_PROMPT = """You extract a structured child profile from a Singapore parent's
free-text description, for a Primary 1 school-fit assistant. Only fill fields you have
direct evidence for in the text — leave everything else null/empty rather than guessing."""


def _keyword_extract(raw_input: str) -> ChildProfile:
    text = raw_input.lower()

    sen_conditions = [name for name, kws in _SEN_KEYWORDS.items() if any(k in text for k in kws)]
    sensory = [name for name, kws in _SENSORY_KEYWORDS.items() if any(k in text for k in kws)]
    ccas = [c for c in _CCA_KEYWORDS if c in text]

    max_commute = None
    m = re.search(r"(\d+)\s*(?:min|minute)", text)
    if m:
        max_commute = int(m.group(1))

    return ChildProfile(
        sen_conditions=sen_conditions,
        sensory_preferences=sensory,
        cca_interests=ccas,
        max_commute_minutes=max_commute,
        social_behaviour_notes=raw_input.strip() or None,
        registration_phase="2C",  # TODO: ask the parent explicitly rather than assuming
        raw_input=raw_input,
    )


def extract_profile(raw_input: str) -> ChildProfile:
    if is_fake():
        return _keyword_extract(raw_input)

    model = get_chat_model().with_structured_output(ChildProfile)
    profile = model.invoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_input},
        ]
    )
    profile.raw_input = raw_input
    if not profile.registration_phase:
        profile.registration_phase = "unknown"
    return profile
