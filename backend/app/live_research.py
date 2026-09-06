"""Small, source-first live research pass for real school comparisons."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from .comparison_schema import ComparisonRequest, Evidence, Requirement

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SINGAPORE = ZoneInfo("Asia/Singapore")
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"


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


def _prompt(request: ComparisonRequest) -> str:
    schools = "\n".join(
        f'- id `{school_id}`: {school_name}'
        for school_id, school_name in zip(request.school_ids, request.school_names or [])
    )
    requirements = "\n".join(
        f'- id `{requirement.id}` ({requirement.topic}, {requirement.priority}): {requirement.details}'
        + (f" Maximum door-to-door commute: {requirement.max_minutes:g} minutes." if requirement.max_minutes else "")
        for requirement in request.requirements
    )
    return f"""We are comparing two Singapore primary schools for a family. Research current public web sources and return only the JSON schema requested.

Schools:
{schools}

Family context:
{request.context or "No additional context."}

Requirements:
{requirements}

Research rules:
1. Search for each school by its exact name, prioritising the school's own site, Singapore MOE pages, and named programme or student-care provider pages. Do not substitute a similarly named school.
2. A finding supports a requirement only when a source directly describes the relevant arrangement. Mark does_not_support only when a source directly says the arrangement is unavailable or does not apply. Otherwise use unclear.
3. Never infer eligibility, admission probability, quality, teacher fit, commute time, or availability from a programme name or from silence. For commute, use unclear unless a source gives a measured journey relevant to this family.
4. Return one finding per useful source, at most two sources per school/requirement. The source URL must be an exact HTTP/S URL that appeared in your search results. If no source is specific enough, omit that school/requirement rather than inventing a source.
5. Keep excerpts short and faithful. Do not include private or sensitive personal information.
"""


def _extract_content(payload: dict[str, Any]) -> str:
    try:
        message = payload["choices"][0]["message"]
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    except (KeyError, IndexError, TypeError):
        pass
    raise LiveResearchError("OpenRouter returned no comparison content.")


def _findings(payload: dict[str, Any], request: ComparisonRequest) -> dict[tuple[str, str], list[Evidence]]:
    try:
        candidate = _strip_json_fence(_extract_content(payload))
        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            start = min((index for index in (candidate.find("{"), candidate.find("[")) if index >= 0), default=-1)
            if start < 0:
                raise
            raw, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except (json.JSONDecodeError, KeyError, TypeError):
        raise LiveResearchError("OpenRouter returned an invalid comparison format.") from None

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
        raise LiveResearchError("OpenRouter returned an invalid comparison format.")

    school_ids = set(request.school_ids)
    requirement_ids = {requirement.id for requirement in request.requirements}
    today = datetime.now(SINGAPORE).date().isoformat()
    output: dict[tuple[str, str], list[Evidence]] = {}
    for index, item in enumerate(findings):
        if not isinstance(item, dict):
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
        if (
            school_id not in school_ids or requirement_id not in requirement_ids
            or outcome not in {"supports", "does_not_support", "unclear"}
            or not all(isinstance(value, str) and value.strip() for value in (title, url, excerpt))
            or not _valid_url(url)
        ):
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
    return output


def research_schools(request: ComparisonRequest) -> dict[tuple[str, str], list[Evidence]]:
    """Research both named schools in one bounded OpenRouter request."""
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
            {"role": "user", "content": _prompt(request)},
        ],
        "tools": [{
            "type": "openrouter:web_search",
            "parameters": {"engine": "auto", "max_results": 3, "max_total_results": 8},
        }],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "school_comparison_research", "strict": True, "schema": _json_schema()},
        },
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
    return _findings(payload, request)
