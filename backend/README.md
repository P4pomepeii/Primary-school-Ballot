# backend — School-Fit Copilot agent graph

The main comparison workflow now runs independently of the original graph:

- `GET /schools` returns requirement topics; the main UI accepts two real school names.
- `POST /compare` researches uncached names with one bounded OpenRouter web-search
  pass, then evaluates must-haves and preferences deterministically.
- No database, real routing or personal admission predictions are used by these
  endpoints. See [the API and evidence rules](../docs/COMPARISON.md).

Set `OPENROUTER_API_KEY` to enable live comparisons. `OPENROUTER_MODEL` defaults to
`google/gemini-2.5-flash` (the `-lite` tier does not reliably return the requested
JSON shape when the web-search tool is active). Results contain source leads for verification; the
API does not save prompts or notes. Live evidence is shared in a bounded,
process-local cache keyed by school name, so repeated users do not trigger another
API call for the same school.

Use Python 3.11+ in a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
MODEL_PROVIDER=fake .venv/bin/uvicorn app.server:app --reload
```

Run all comparison and legacy tests with `.venv/bin/python -m pytest -q`.
If your environment is named `venv`, use that directory instead.

The following sections describe the **legacy discovery graph** at `POST /invoke`.

A LangGraph `StateGraph` that turns a parent's free-text description of
their child into ranked, explained primary-school recommendations. See
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the full pipeline
diagram and design rationale.

## Run locally

```bash
.venv/bin/python -m pip install -r requirements.txt
MODEL_PROVIDER=fake .venv/bin/uvicorn app.server:app --reload
```

This starts the API at `http://localhost:8000`:

- `POST /invoke` — `{"message": "..."}` → `{"results": [...]}`
- `GET /health`

Try it:

```bash
curl -s localhost:8000/invoke \
  -H 'content-type: application/json' \
  -d '{"message": "My son has ADHD and loves swimming. We are at Bishan, Phase 2B, want under 20 min commute."}' | python3 -m json.tool
```

## Run the tests

```bash
MODEL_PROVIDER=fake python3 -m pytest -q
```

## Switching model providers

The exported environment variable `MODEL_PROVIDER` controls `app/llm.py` for the
legacy discovery graph. `.env` is not automatically loaded by this backend:

| value     | needs                                              | matches |
|-----------|-----------------------------------------------------|---------|
| `fake`    | nothing — deterministic keyword extractor + template synthesis | local dev / CI |
| `groq`    | `GROQ_API_KEY`                                       | hackathon Session 1 labs |
| `bedrock` | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / region | hackathon Session 2 labs, AgentCore deployment |

## Layout

```
app/
  schema.py          Pydantic models shared across the whole pipeline
  data/schools.json  seed data — 5 FICTIONAL schools, replace before real use
  tools/
    sen_support.py   SEN/programme-fit scoring (rule-based, explainable)
    commute.py       distance/commute estimate (haversine placeholder — swap for OneMap)
    admission_odds.py  Bayesian (Beta-Binomial) odds model
    community.py     community-experience evidence (SYNTHETIC — see docstring, PDPA note)
  llm.py             MODEL_PROVIDER switch (fake / groq / bedrock)
  extract.py         free text -> ChildProfile
  synthesize.py      evidence -> per-school natural-language explanation + ranking
  graph.py           the LangGraph StateGraph wiring all of the above together
  server.py          FastAPI wrapper; handler() doubles as the AgentCore entrypoint
tests/
  test_graph.py      end-to-end smoke test, runs fully offline (MODEL_PROVIDER=fake)
```

## Before demo day

- Replace `app/data/schools.json` with real, current school data.
- Replace `app/tools/commute.py`'s haversine placeholder with real OneMap
  (Singapore) geocoding/routing — a nice Singapore-specific judge-facing
  detail.
- Read `app/tools/community.py`'s docstring before adding real parent
  testimonials — synthetic data is fine for a demo as long as you disclose
  it; scraped real data about children's SEN status is not.
- Tighten CORS in `server.py` (currently wide open for local dev).
- Deploy this graph to AWS Bedrock AgentCore; point the frontend's
  `BACKEND_URL` at the deployed endpoint instead of localhost.
