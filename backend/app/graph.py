"""The orchestrator graph.

    START -> extract_profile -> select_candidates -> [4 sub-agents, parallel] -> synthesize -> END
                                                        |sen_support|
                                                        |commute    |
                                                        |admission  |
                                                        |community  |

This is the DeepAgents sub-agent pattern from your training deck (§5) applied
to the solution doc's 4 comparison dimensions — one sub-agent per dimension,
fanned out in parallel, joined before synthesis. Deploy this graph itself to
Bedrock AgentCore (§6); the Vercel frontend only ever calls the deployed
endpoint, it never runs this graph directly.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from .extract import extract_profile as _extract_profile
from .schema import ChildProfile, SchoolFitEvidence, SchoolFitResult
from .synthesize import rank_results, synthesize_school
from .tools import admission_odds_tool, commute_tool, community_tool, list_school_ids, sen_support_tool

MAX_CANDIDATES = 5  # keep small for a hackathon demo; widen once commute/geocoding is real


class State(TypedDict):
    raw_input: str
    profile: ChildProfile
    candidate_school_ids: list[str]
    evidence: Annotated[list[SchoolFitEvidence], operator.add]
    results: list[SchoolFitResult]


def extract_profile_node(state: State) -> dict:
    profile = _extract_profile(state["raw_input"])
    return {"profile": profile}


def select_candidates_node(state: State) -> dict:
    # Demo scope: consider every seeded school. Replace with a real
    # distance-band prefilter (e.g. "within profile.max_commute_minutes")
    # once geocoding is wired up in tools/commute.py.
    return {"candidate_school_ids": list_school_ids()[:MAX_CANDIDATES]}


def _sen_node(state: State) -> dict:
    profile = state["profile"]
    return {"evidence": [sen_support_tool(profile, sid) for sid in state["candidate_school_ids"]]}


def _commute_node(state: State) -> dict:
    profile = state["profile"]
    return {"evidence": [commute_tool(profile, sid) for sid in state["candidate_school_ids"]]}


def _odds_node(state: State) -> dict:
    profile = state["profile"]
    return {"evidence": [admission_odds_tool(profile, sid) for sid in state["candidate_school_ids"]]}


def _community_node(state: State) -> dict:
    profile = state["profile"]
    return {"evidence": [community_tool(profile, sid) for sid in state["candidate_school_ids"]]}


def synthesize_node(state: State) -> dict:
    by_school: dict[str, list[SchoolFitEvidence]] = {}
    for e in state["evidence"]:
        by_school.setdefault(e.school_id, []).append(e)

    results = [synthesize_school(sid, ev) for sid, ev in by_school.items()]
    return {"results": rank_results(results)}


def build_graph():
    g = StateGraph(State)

    g.add_node("extract_profile", extract_profile_node)
    g.add_node("select_candidates", select_candidates_node)
    g.add_node("sen_support", _sen_node)
    g.add_node("commute", _commute_node)
    g.add_node("admission_odds", _odds_node)
    g.add_node("community", _community_node)
    g.add_node("synthesize", synthesize_node)

    g.add_edge(START, "extract_profile")
    g.add_edge("extract_profile", "select_candidates")

    # Fan out — all four run in the same LangGraph superstep.
    for sub_agent in ("sen_support", "commute", "admission_odds", "community"):
        g.add_edge("select_candidates", sub_agent)
        g.add_edge(sub_agent, "synthesize")

    g.add_edge("synthesize", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run(raw_input: str) -> list[SchoolFitResult]:
    graph = get_graph()
    final_state = graph.invoke({"raw_input": raw_input, "evidence": []})
    return final_state["results"]
