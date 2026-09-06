"""Small, source-first live research pass for real school comparisons."""
from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from .comparison_schema import ComparisonRequest, Evidence, Requirement

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SINGAPORE = ZoneInfo("Asia/Singapore")
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
logger = logging.getLogger("uvicorn.error")

_REQUIREMENT_PATTERNS = {
    "quiet_space": (
        r"\bquiet (?:space|room|area)\b", r"\bsensory (?:space|room|break)\b",
        r"\bcalm (?:space|room|corner)\b", r"\bwellness room\b",
    ),
    "learning_support": (
        r"\blearning support\b", r"\blearning and behavioural support\b",
        r"\ballied educator\b", r"\bspecial educational needs?\b", r"\bsen officers?\b",
    ),
    "student_care": (
        r"\bstudent care\b", r"\bschoolcare\b", r"\bafter[- ]school care\b",
    ),
    "workload": (r"\bhomework\b", r"\bworkload\b"),
    "social_inclusion": (
        r"\bsocial inclusion\b", r"\bpeer support\b", r"\bfriendship\b",
        r"\banti[- ]bullying\b", r"\bstudent well[- ]being\b",
    ),
    "cca": (
        r"\bco-curricular\b", r"\bcca(?:s)?\b", r"\bclubs? and societies\b",
    ),
}
_SEARCH_TERMS = {
    "quiet_space": '"quiet space" OR "sensory room" OR "calm room"',
    "learning_support": '"learning support" OR "allied educator" OR "special educational needs"',
    "student_care": '"student care" OR schoolcare',
    "workload": "homework OR workload",
    "social_inclusion": '"peer support" OR "student well-being" OR bullying',
    "cca": 'CCA OR "co-curricular activities"',
}
_GENERIC_SCHOOL_WORDS = {"primary", "school", "singapore", "the"}


class LiveResearchError(RuntimeError):
    """Raised when the live source pass cannot produce a safe comparison."""


def _json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "school_id": {"type": "string"},
                        "requirement_id": {"type": "string"},
                        "outcome": {"type": "string", "enum": ["supports", "does_not_support", "unclear"]},
                        "source_title": {"type": "string"},
                        "source_url": {"type": "string"},
                        "source_excerpt": {"type": "string"},
                    },
                    "required": [
                        "school_id", "requirement_id", "outcome", "source_title",
                        "source_url", "source_excerpt",
                    ],
                },
            },
        },
        "required": ["findings"],
    }


def _strip_json_fence(content: str) -> str:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()
    # Some providers add prose or markdown around JSON despite response_format.
    # Scan for the first complete object/array rather than trusting the first
    # brace, which may occur in a sentence or a code example.
    decoder = json.JSONDecoder()
    for start, marker in enumerate(content):
        if marker not in "[{":
            continue
        try:
            _, end = decoder.raw_decode(content[start:])
            return content[start:start + end]
        except json.JSONDecodeError:
            continue
    return content


def _valid_url(value: str) -> bool:
    return bool(re.match(r"^https?://[^\s]+$", value, flags=re.IGNORECASE))


def _message(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise LiveResearchError("OpenRouter returned no comparison content.") from None
    if not isinstance(message, dict):
        raise LiveResearchError("OpenRouter returned no comparison content.")
    return message


def _prompt(
    request: ComparisonRequest,
    school_ids: Sequence[str] | None = None,
    requirements: Sequence[Requirement] | None = None,
) -> str:
    selected_school_ids = list(school_ids or request.school_ids)
    names_by_id = dict(zip(request.school_ids, request.school_names or []))
    schools = "\n".join(
        f'- id `{school_id}`: {names_by_id[school_id]}'
        for school_id in selected_school_ids
    )
    selected_requirements = list(requirements or request.requirements)
    requirement_lines = "\n".join(
        f'- id `{requirement.id}` ({requirement.topic}, {requirement.priority}): {requirement.details}'
        + (f" Maximum door-to-door commute: {requirement.max_minutes:g} minutes." if requirement.max_minutes else "")
        for requirement in selected_requirements
    )
    search_targets = "\n".join(
        f'- `{school_id}` / `{requirement.id}`: "{names_by_id[school_id]}" '
        f'{_SEARCH_TERMS[requirement.topic]} MOE'
        for school_id in selected_school_ids
        for requirement in selected_requirements
        if requirement.topic in _SEARCH_TERMS
    ) or "- No public-web target is suitable; return an empty findings array."
    return f"""We are researching one or more Singapore primary schools for a family. Research current public web sources and return only the JSON schema requested.

Schools:
{schools}

Family context:
{request.context or "No additional context."}

Requirements:
{requirement_lines}

Run a separate targeted web search for every target below before answering:
{search_targets}

Return exactly one JSON object in this shape:
{{"findings":[{{"school_id":"one of the ids above","requirement_id":"one of the ids above","outcome":"supports|does_not_support|unclear","source_title":"page title","source_url":"exact https URL","source_excerpt":"short faithful excerpt"}}]}}
Use an empty findings array when no source qualifies.

Research rules:
1. Use the web-search tool for every target listed above. Search by the exact school name and target terms, prioritising the school's own site, Singapore MOE pages, and named programme or student-care provider pages. Do not substitute a similarly named school.
2. A finding supports a requirement only when a source directly describes the relevant arrangement. Mark does_not_support only when a source directly says the arrangement is unavailable or does not apply. Otherwise use unclear.
3. Never infer eligibility, admission probability, quality, teacher fit, commute time, or availability from a programme name or from silence. For commute, use unclear unless a source gives a measured journey relevant to this family.
4. Return one finding per useful source, at most two sources per school/requirement. The source URL must be an exact HTTP/S URL that appeared in your search results. If no source is specific enough, omit that school/requirement rather than inventing a source.
5. Keep excerpts short and faithful. Do not include private or sensitive personal information.

Output format — return ONLY a single JSON object shaped exactly like this example (a flat "findings" array; do not nest by school or requirement, do not use any other key names, do not wrap in prose or markdown):
{{
  "findings": [
    {{
      "school_id": {json.dumps(request.school_ids[0])},
      "requirement_id": {json.dumps(request.requirements[0].id)},
      "outcome": "supports",
      "source_title": "Example Source Title",
      "source_url": "https://example.gov.sg/page",
      "source_excerpt": "A short, faithful excerpt from that exact source."
    }}
  ]
}}
Every item in "findings" must have exactly these six fields: school_id, requirement_id, outcome, source_title, source_url, source_excerpt. If you find nothing specific enough for any school/requirement, return {{"findings": []}} rather than any other shape.
"""


def _extract_content(payload: dict[str, Any]) -> str:
    content = _message(payload).get("content")
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    raise LiveResearchError("OpenRouter returned no comparison content.")


def _normalise_words(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _official_school_source(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ("moe.gov.sg", "moe.edu.sg")
    )


def _citation_matches_school(school_name: str, title: str, content: str, url: str) -> bool:
    normalised_name = _normalise_words(school_name)
    normalised_title = _normalise_words(title)
    if normalised_name and normalised_name in normalised_title:
        return True
    signature = "".join(
        word for word in normalised_name.split()
        if word not in _GENERIC_SCHOOL_WORDS
    )
    normalised_location = "".join(re.findall(r"[a-z0-9]+", url.casefold()))
    if len(signature) >= 4 and signature in normalised_location:
        return True
    hostname = (urlparse(url).hostname or "").casefold().rstrip(".")
    return (
        (hostname == "moe.gov.sg" or hostname.endswith(".moe.gov.sg"))
        and normalised_name in _normalise_words(content)
    )


def _matching_pattern(requirement: Requirement, text: str) -> str | None:
    for pattern in _REQUIREMENT_PATTERNS.get(requirement.topic, ()):
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def _citation_excerpt(content: str, title: str, pattern: str) -> str:
    text = re.sub(r"\s+", " ", content).strip() or title.strip()
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return text[:600]
    start = max(0, match.start() - 140)
    end = min(len(text), match.end() + 360)
    excerpt = text[start:end].strip()
    if start:
        excerpt = f"…{excerpt}"
    if end < len(text):
        excerpt = f"{excerpt}…"
    return excerpt


def _annotation_findings(
    payload: dict[str, Any],
    request: ComparisonRequest,
    school_ids: Sequence[str] | None = None,
    requirements: Sequence[Requirement] | None = None,
) -> tuple[dict[tuple[str, str], list[Evidence]], dict[str, int]]:
    """Turn official citation snippets into non-conclusive source leads."""
    annotations = _message(payload).get("annotations")
    stats = {"seen": 0, "non_url": 0, "non_official": 0, "school_mismatch": 0, "accepted": 0}
    if not isinstance(annotations, list):
        return {}, stats

    selected_school_ids = list(school_ids or request.school_ids)
    selected_requirements = list(requirements or request.requirements)
    names_by_id = dict(zip(request.school_ids, request.school_names or []))
    today = datetime.now(SINGAPORE).date().isoformat()
    output: dict[tuple[str, str], list[Evidence]] = {}
    seen_urls: dict[tuple[str, str], set[str]] = {}
    for index, annotation in enumerate(annotations):
        stats["seen"] += 1
        citation = annotation.get("url_citation") if isinstance(annotation, dict) else None
        if not isinstance(citation, dict):
            stats["non_url"] += 1
            continue
        url = citation.get("url")
        title = citation.get("title")
        content = citation.get("content")
        if not isinstance(url, str) or not _valid_url(url):
            stats["non_url"] += 1
            continue
        title = title.strip() if isinstance(title, str) else ""
        content = content.strip() if isinstance(content, str) else ""
        if not _official_school_source(url):
            stats["non_official"] += 1
            continue

        matched_school = False
        for school_id in selected_school_ids:
            school_name = names_by_id.get(school_id, "")
            if not _citation_matches_school(school_name, title, content, url):
                continue
            matched_school = True
            searchable = f"{title}\n{url}\n{content}"
            for requirement in selected_requirements:
                pattern = _matching_pattern(requirement, searchable)
                if pattern is None:
                    continue
                key = (school_id, requirement.id)
                if url in seen_urls.setdefault(key, set()) or len(output.get(key, [])) >= 2:
                    continue
                seen_urls[key].add(url)
                source_title = title or urlparse(url).netloc or "Official school source"
                summary = _citation_excerpt(content, source_title, pattern)
                if not summary:
                    continue
                output.setdefault(key, []).append(Evidence(
                    id=f"live:annotation:{index}:{school_id}:{requirement.id}",
                    source_type="published_information",
                    source_label=f"Official citation retrieved via OpenRouter — {source_title}",
                    source_url=url.strip(), observed_on=today,
                    summary=summary, outcome="unclear",
                    commute_minutes=None, is_demo=False,
                ))
                stats["accepted"] += 1
        if not matched_school:
            stats["school_mismatch"] += 1
    return output, stats


def _findings(
    payload: dict[str, Any],
    request: ComparisonRequest,
    school_ids: Sequence[str] | None = None,
    requirements: Sequence[Requirement] | None = None,
) -> dict[tuple[str, str], list[Evidence]]:
    annotation_output, annotation_stats = _annotation_findings(
        payload, request, school_ids, requirements,
    )
    try:
        candidate = _strip_json_fence(_extract_content(payload))
        if not candidate.strip():
            logger.info(
                "live_research_parse content=empty annotation_seen=%d annotation_accepted=%d",
                annotation_stats["seen"], annotation_stats["accepted"],
            )
            return annotation_output
        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            start = min((index for index in (candidate.find("{"), candidate.find("[")) if index >= 0), default=-1)
            if start < 0:
                raise
            raw, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning(
            "live_research_parse content=invalid used_annotations=%d",
            annotation_stats["accepted"],
        )
        return annotation_output

    # Models occasionally wrap findings by school/requirement even when the
    # provider accepts the requested JSON schema. Flatten both that shape and the
    # canonical {"findings": [...]} shape before applying strict validation.
    if isinstance(raw, dict) and isinstance(raw.get("schools"), list):
        findings = []
        for school in raw["schools"]:
            if not isinstance(school, dict):
                continue
            school_id = school.get("school_id") or school.get("id")
            for requirement in school.get("requirements", []):
                if not isinstance(requirement, dict):
                    continue
                requirement_id = requirement.get("requirement_id") or requirement.get("id")
                for finding in requirement.get("findings", []):
                    if isinstance(finding, dict):
                        findings.append({
                            **finding,
                            "school_id": school_id,
                            "requirement_id": requirement_id,
                        })
    elif isinstance(raw, dict):
        findings = raw.get("findings", [])
    elif isinstance(raw, list) and any(
        isinstance(group, dict) and isinstance(group.get("requirements"), list)
        for group in raw
    ):
        findings = []
        for school in raw:
            if not isinstance(school, dict):
                continue
            school_id = school.get("school_id") or school.get("id")
            for requirement in school.get("requirements", []):
                if not isinstance(requirement, dict):
                    continue
                finding = requirement.get("finding")
                if not isinstance(finding, dict):
                    continue
                findings.append({
                    "school_id": school_id,
                    "requirement_id": requirement.get("requirement_id") or requirement.get("id"),
                    "outcome": requirement.get("outcome") or requirement.get("finding_type"),
                    "source_url": finding.get("source_url") or finding.get("url"),
                    "source_excerpt": finding.get("source_excerpt") or finding.get("excerpt"),
                    "source_title": finding.get("source_title") or finding.get("title"),
                })
    elif isinstance(raw, list):
        findings = []
        for group in raw:
            if not isinstance(group, dict):
                continue
            nested = group.get("findings")
            if isinstance(nested, list):
                findings.extend({**item, "school_id": group.get("school_id"), "requirement_id": group.get("requirement_id")} for item in nested if isinstance(item, dict))
            else:
                findings.append(group)
    else:
        findings = []
    if not isinstance(findings, list):
        logger.warning(
            "live_research_parse findings=invalid used_annotations=%d",
            annotation_stats["accepted"],
        )
        return annotation_output

    selected_school_ids = set(school_ids or request.school_ids)
    selected_requirement_ids = {requirement.id for requirement in (requirements or request.requirements)}
    today = datetime.now(SINGAPORE).date().isoformat()
    output: dict[tuple[str, str], list[Evidence]] = {}
    rejected = {"not_object": 0, "scope": 0, "outcome": 0, "fields": 0, "url": 0}
    for index, item in enumerate(findings):
        if not isinstance(item, dict):
            rejected["not_object"] += 1
            continue
        school_id = item.get("school_id")
        requirement_id = item.get("requirement_id")
        outcome = item.get("outcome") or item.get("support") or (
            item.get("id") if item.get("id") in {"supports", "does_not_support", "unclear"} else None
        )
        title = item.get("source_title") or item.get("source_label")
        url = item.get("source_url") or item.get("url")
        excerpt = item.get("source_excerpt") or item.get("excerpt")
        if isinstance(url, str) and not title:
            title = urlparse(url).netloc or "Public web source"
        if school_id not in selected_school_ids or requirement_id not in selected_requirement_ids:
            rejected["scope"] += 1
            continue
        if outcome not in {"supports", "does_not_support", "unclear"}:
            rejected["outcome"] += 1
            continue
        if not all(isinstance(value, str) and value.strip() for value in (title, url, excerpt)):
            rejected["fields"] += 1
            continue
        if not _valid_url(url):
            rejected["url"] += 1
            continue
        key = (school_id, requirement_id)
        if len(output.get(key, [])) >= 2:
            continue
        output.setdefault(key, []).append(Evidence(
            id=f"live:{index}:{school_id}:{requirement_id}",
            source_type="published_information",
            source_label=f"Live web research via OpenRouter — {title.strip()}",
            source_url=url.strip(), observed_on=today,
            summary=excerpt.strip(), outcome=outcome,
            commute_minutes=None, is_demo=False,
        ))
    model_evidence_count = sum(len(items) for items in output.values())
    for key, sources in annotation_output.items():
        if key not in output:
            output[key] = sources
    logger.info(
        "live_research_parse content=structured model_items=%d model_evidence=%d "
        "annotation_seen=%d annotation_accepted=%d rejected_not_object=%d "
        "rejected_scope=%d rejected_outcome=%d rejected_fields=%d rejected_url=%d",
        len(findings), model_evidence_count, annotation_stats["seen"],
        annotation_stats["accepted"], rejected["not_object"], rejected["scope"],
        rejected["outcome"], rejected["fields"], rejected["url"],
    )
    return output


def research_schools(
    request: ComparisonRequest,
    school_ids: Sequence[str] | None = None,
    requirements: Sequence[Requirement] | None = None,
) -> dict[tuple[str, str], list[Evidence]]:
    """Research the selected named schools in one bounded OpenRouter request."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise LiveResearchError("Live research is not configured.")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a careful research assistant. Follow the source and uncertainty rules exactly. Return only the requested JSON.",
            },
            {"role": "user", "content": _prompt(request, school_ids, requirements)},
        ],
        "tools": [{
            "type": "openrouter:web_search",
            "parameters": {"engine": "auto", "max_results": 3, "max_total_results": 8},
        }],
        "temperature": 0.1,
        "max_tokens": 4500,
    }
    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://school-fit-comparison.fly.dev",
                "X-Title": "School-Fit Copilot",
            },
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise LiveResearchError("Live research could not be completed. Please try again shortly.") from None
    result = _findings(payload, request, school_ids, requirements)
    message = _message(payload)
    content = message.get("content")
    annotations = message.get("annotations")
    selected_school_count = len(school_ids or request.school_ids)
    selected_requirement_count = len(requirements or request.requirements)
    logger.info(
        "live_research_complete request_id=%s model=%s provider=%s schools=%d "
        "requirements=%d content_type=%s annotations=%d cells=%d evidence=%d",
        response.headers.get("x-request-id", "unavailable"), model,
        payload.get("provider", "unavailable") if isinstance(payload, dict) else "unavailable",
        selected_school_count, selected_requirement_count, type(content).__name__,
        len(annotations) if isinstance(annotations, list) else 0,
        len(result), sum(len(items) for items in result.values()),
    )
    return result
