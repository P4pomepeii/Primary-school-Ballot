# Architecture — School-Fit Copilot

> This document describes the original discovery graph, still available at
> `/discover` and `POST /invoke`. The main app now uses the deterministic
> [two-school comparison workflow](COMPARISON.md). Its evidence rules and
> assessments are separate from the legacy graph's scores and admission estimates.

## The pipeline

```
parent's free-text description
        │
        ▼
 extract_profile          ChildProfile (structured: SEN needs, sensory
   (LangGraph node)        prefs, CCA interests, alumni, home address,
        │                  ballot phase, max commute)
        ▼
 select_candidates         shortlist of school_ids to evaluate
   (LangGraph node)         (currently: all seed schools; swap in a
        │                   real geo/phase filter later)
        │
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
   sen_support      commute      admission_odds   community
   (tool node)    (tool node)     (tool node)     (tool node)
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                        │  (fan-in via Annotated[list, operator.add])
                        ▼
                  synthesize_node
             (one LLM call per school: turns
              4 evidence rows into a plain-
              English "why this fits" summary,
              then ranks all schools)
                        │
                        ▼
              list[SchoolFitResult]
```

This is the **DeepAgents / sub-agent-per-domain** pattern: each data source
(SEN support, commute, admission odds, community sentiment) is its own
tool-calling node with a narrow, stable function signature — the same shape
as an MCP tool, even though today they're plain Python functions reading
`data/schools.json`. Swapping any one of them for a real MCP server later
(e.g. a live OneMap routing server) doesn't touch the graph.

`extract_profile` and `synthesize` are the only two nodes that call an LLM.
Everything in between is deterministic and explainable — important for a
product parents will use to make a high-stakes decision about their child.

## Why not "a neural network that learns"

The original pitch was "a neural network that learns and adjusts" from
parent inputs. Three deliberate departures from that, kept from the earlier
discussion:

1. **Admission odds** use a Bayesian (Beta-Binomial) model over each
   school's historical vacancy/applicant counts, not a trained net. A few
   years × a handful of schools is nowhere near enough data to train
   anything — a neural net there would just memorize noise. The Bayesian
   model degrades gracefully with sparse data (falls back toward the prior)
   and is auditable: you can always show *why* it produced a number.
2. **"Learning from inputs" happens via a growing evidence corpus**
   (`community.py`), not weight updates. As more (consented, real) parent
   experiences come in, they become more retrievable evidence for the
   `community` tool — this is RAG, not retraining. It's the practical way to
   incorporate new information continuously without an ML pipeline,
   labelled data, or a retraining/eval cycle a hackathon team can't build in
   a weekend.
3. **Fit scoring is rule-based and inspectable** (`sen_support.py`), so every
   number the app shows a parent traces back to a concrete, stated reason —
   this *is* the product's differentiator per the original problem
   statement ("explains *why* a school fits, not just ranks it"). A neural
   net optimizing an opaque score would undermine that.

If real usage data eventually justifies it, a learned re-ranker could sit
*on top of* this evidence (e.g. logistic regression over the four evidence
scores, trained on which recommendations parents said were useful) — but
that's a v2 problem, not a hackathon-weekend one.

## Data flow: PDPA note

`community.py`'s docstring flags this explicitly: the four sample entries
are synthetic and labelled as such. Real parent-shared experiences about a
child (especially SEN status) are personal data about a minor — don't scrape
forum/Facebook-group posts into this file without consent. For a demo, either
hand-collect a small consented sample and disclose that in the pitch, or keep
the synthetic data and say so.

## Deployment target

- **Backend**: `backend/app/graph.py`'s `run()` (wrapped by `server.py`'s
  `handler()`) is written to be the entrypoint for **AWS Bedrock
  AgentCore** — framework-agnostic, single `message: str` in, structured
  result out. `server.py` also exposes it as a plain FastAPI app
  (`POST /invoke`) so it runs anywhere (local dev, a container, AgentCore)
  without code changes.
- **Frontend**: a Next.js app on **Vercel**. It never talks to the LLM or
  AWS directly — it calls its own `/api/chat` route, which proxies
  server-side to wherever the backend is running (`BACKEND_URL`). This keeps
  all credentials out of the browser and means the backend can move (local →
  AgentCore) without a frontend redeploy, just an env var change.

## Provider switch

`backend/app/llm.py` reads `MODEL_PROVIDER` (`fake` / `groq` / `bedrock`).
`fake` is the default and needs no API key — it drives a deterministic
keyword extractor and template synthesizer, which is what let this scaffold
be built and tested (`pytest`, 2/2 passing) with zero credentials. Switch to
`groq` for the hackathon's Session 1 labs, or `bedrock` to match Session 2 /
AgentCore deployment.
