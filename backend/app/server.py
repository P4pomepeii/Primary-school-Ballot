"""FastAPI wrapper around the graph.

Two jobs:
  1. Local dev server (`uvicorn app.server:app --reload`) — this is what the
     Vercel frontend's /api/chat route calls during development.
  2. The same `handler()` function is what you wrap for a Bedrock AgentCore
     entrypoint (§6 of your training) at deploy time — keep the actual graph
     logic here, not scattered into framework-specific glue.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from .compare import compare_schools, get_catalogue
from .comparison_schema import CatalogueResponse, ComparisonRequest, ComparisonResponse, Observation, Requirement
from .graph import run
from .live_research import LiveResearchError, research_schools
from .schema import SchoolFitResult

app = FastAPI(title="School-Fit Copilot")

_LIVE_CACHE_TTL_SECONDS = 10 * 60
_LIVE_CACHE_MAX_ENTRIES = 32
_live_cache: dict[str, tuple[float, dict]] = {}

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
    cache_key = json.dumps(req.model_dump(exclude={"observations"}), sort_keys=True, separators=(",", ":"))
    cached = _live_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] <= _LIVE_CACHE_TTL_SECONDS:
        return compare_schools(req, live_evidence=cached[1])
    try:
        live_evidence = research_schools(req)
    except LiveResearchError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})
    if len(_live_cache) >= _LIVE_CACHE_MAX_ENTRIES:
        oldest_key = min(_live_cache, key=lambda key: _live_cache[key][0])
        _live_cache.pop(oldest_key, None)
    _live_cache[cache_key] = (time.monotonic(), live_evidence)
    return compare_schools(req, live_evidence=live_evidence)


app.include_router(comparison_routes)
