"""FastAPI wrapper around the graph.

Two jobs:
  1. Local dev server (`uvicorn app.server:app --reload`) — this is what the
     Vercel frontend's /api/chat route calls during development.
  2. The same `handler()` function is what you wrap for a Bedrock AgentCore
     entrypoint (§6 of your training) at deploy time — keep the actual graph
     logic here, not scattered into framework-specific glue.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from .compare import compare_schools, get_catalogue
from .comparison_schema import CatalogueResponse, ComparisonRequest, ComparisonResponse, Evidence, Observation, Requirement
from .graph import run
from .live_research import LiveResearchError, research_schools
from .schema import SchoolFitResult

app = FastAPI(title="School-Fit Copilot")

_LIVE_CACHE_MAX_SCHOOLS = 128


@dataclass
class _LiveSchoolCacheEntry:
    covered_requirements: set[tuple[str, str, float | None]] = field(default_factory=set)
    findings: dict[tuple[str, str, float | None], list[Evidence]] = field(default_factory=dict)


# This cache is deliberately process-global: every user routed to this Fly
# machine shares the same researched-school results. It is bounded but does
# not expire, so a school is only sent to OpenRouter again after eviction or a
# process restart/redeploy.
_live_school_cache: OrderedDict[str, _LiveSchoolCacheEntry] = OrderedDict()
_live_cache_lock = Lock()
_live_research_lock = Lock()


def _school_cache_key(name: str) -> str:
    return " ".join(name.casefold().split())


def _requirement_cache_key(requirement: Requirement) -> tuple[str, str, float | None]:
    return (
        requirement.topic,
        " ".join(requirement.details.casefold().split()),
        requirement.max_minutes,
    )


def _relabel_cached_evidence(
    evidence: Evidence,
    school_id: str,
    requirement_id: str,
    index: int,
) -> Evidence:
    return evidence.model_copy(update={"id": f"live:cached:{school_id}:{requirement_id}:{index}"})


def _read_cached_live_evidence(
    request: ComparisonRequest,
) -> tuple[dict[tuple[str, str], list[Evidence]], list[str]]:
    """Return reusable evidence and ids for schools never seen by this process."""
    evidence: dict[tuple[str, str], list[Evidence]] = {}
    uncached_school_ids: list[str] = []
    with _live_cache_lock:
        for school_id, school_name in zip(request.school_ids, request.school_names or []):
            cache_key = _school_cache_key(school_name)
            entry = _live_school_cache.get(cache_key)
            if entry is None:
                uncached_school_ids.append(school_id)
                continue
            _live_school_cache.move_to_end(cache_key)
            for requirement in request.requirements:
                requirement_key = _requirement_cache_key(requirement)
                if requirement_key not in entry.covered_requirements:
                    continue
                evidence[(school_id, requirement.id)] = [
                    _relabel_cached_evidence(item, school_id, requirement.id, index)
                    for index, item in enumerate(entry.findings.get(requirement_key, []))
                ]
    return evidence, uncached_school_ids


def _store_live_evidence(
    request: ComparisonRequest,
    researched_school_ids: list[str],
    evidence: dict[tuple[str, str], list[Evidence]],
) -> None:
    names_by_id = dict(zip(request.school_ids, request.school_names or []))
    with _live_cache_lock:
        for school_id in researched_school_ids:
            school_name = names_by_id[school_id]
            cache_key = _school_cache_key(school_name)
            entry = _LiveSchoolCacheEntry()
            for requirement in request.requirements:
                requirement_key = _requirement_cache_key(requirement)
                entry.covered_requirements.add(requirement_key)
                entry.findings[requirement_key] = list(evidence.get((school_id, requirement.id), []))
            _live_school_cache[cache_key] = entry
            _live_school_cache.move_to_end(cache_key)
        while len(_live_school_cache) > _LIVE_CACHE_MAX_SCHOOLS:
            _live_school_cache.popitem(last=False)

# Tighten this before deploying anywhere real — wide open for local dev only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvokeRequest(BaseModel):
    message: str


class InvokeResponse(BaseModel):
    results: list[SchoolFitResult]


def handler(message: str) -> list[SchoolFitResult]:
    """The AgentCore-deployable entrypoint. Keep this framework-agnostic."""
    return run(message)


@app.post("/invoke", response_model=InvokeResponse)
def invoke(req: InvokeRequest) -> InvokeResponse:
    return InvokeResponse(results=handler(req.message))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class _ComparisonRoute(APIRoute):
    """Keep comparison responses private, including redacted validation errors."""

    def get_route_handler(self):
        original = super().get_route_handler()
        safe_fields = {"body", "query", "path", "header"} | {
            field for model in (ComparisonRequest, Requirement, Observation)
            for field in model.model_fields
        }

        async def route_handler(request: Request):
            try:
                response = await original(request)
            except RequestValidationError as exc:
                # Input and ctx may contain personal details, as can unknown field names.
                # Validator messages are fixed text and never interpolate submitted values.
                details = [{
                    "loc": [part if isinstance(part, int) or part in safe_fields else "[field]"
                            for part in error["loc"]],
                    "msg": error["msg"], "type": error["type"],
                } for error in exc.errors()]
                response = JSONResponse(status_code=422, content={"detail": details})
            response.headers["Cache-Control"] = "no-store"
            return response

        return route_handler


comparison_routes = APIRouter(route_class=_ComparisonRoute)


@comparison_routes.get("/schools", response_model=CatalogueResponse)
def schools() -> CatalogueResponse:
    return get_catalogue()


@comparison_routes.post("/compare", response_model=ComparisonResponse)
def compare(req: ComparisonRequest) -> ComparisonResponse:
    if req.school_names is None:
        return compare_schools(req)
    live_evidence, uncached_school_ids = _read_cached_live_evidence(req)
    if uncached_school_ids:
        # Recheck after waiting so concurrent first-time requests share one
        # OpenRouter call rather than creating an API-cost race.
        with _live_research_lock:
            live_evidence, uncached_school_ids = _read_cached_live_evidence(req)
            if uncached_school_ids:
                try:
                    newly_researched = research_schools(req, school_ids=uncached_school_ids)
                except LiveResearchError as exc:
                    return JSONResponse(status_code=503, content={"error": str(exc)})
                _store_live_evidence(req, uncached_school_ids, newly_researched)
                live_evidence.update(newly_researched)
    return compare_schools(req, live_evidence=live_evidence)


app.include_router(comparison_routes)
