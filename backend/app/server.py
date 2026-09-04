"""FastAPI wrapper around the graph.

Two jobs:
  1. Local dev server (`uvicorn app.server:app --reload`) — this is what the
     Vercel frontend's /api/chat route calls during development.
  2. The same `handler()` function is what you wrap for a Bedrock AgentCore
     entrypoint (§6 of your training) at deploy time — keep the actual graph
     logic here, not scattered into framework-specific glue.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .graph import run
from .schema import SchoolFitResult

app = FastAPI(title="School-Fit Copilot")

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
