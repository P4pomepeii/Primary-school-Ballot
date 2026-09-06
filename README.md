# School-Fit Copilot

A Singapore primary-school decision workspace built with Next.js and FastAPI.
Compare **two schools** against a family's requirements, inspect evidence and gaps,
then record what you learn to update the comparison.

## What you can do

- Choose two of the five fictional demo schools.
- Describe your deciding concern and select requirements: quiet space, learning
  support, student care, commute, workload, inclusion, CCAs, or a custom need.
- Separate must-haves from preferences. An unmet must-have cannot be offset by
  strengths elsewhere; schools stay in the order you selected, without a fit score.
- Inspect the source, date and context of each piece of information.
- Record school responses, published sources, parent experiences or family observations.
- See which requirements changed and which questions to ask next.
- Remove obsolete or incorrect notes and recalculate the comparison.

**All school records and seed snippets are fictional.** They never establish that
a requirement is met. Parent-entered information remains labelled as such; the app
does not independently verify it. Another parent's experience supplies context but
cannot resolve a requirement. No personal admission probabilities are generated
in the comparison workflow.

The original LangGraph discovery prototype remains at `/discover` and
`POST /invoke`. It still uses the original placeholder scoring and data.

## Run locally

Use Python **3.11+** and Node **20+**. The comparison requires no model or API keys.

```bash
# Terminal 1, from the repository root
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
MODEL_PROVIDER=fake .venv/bin/uvicorn app.server:app --reload
```

```bash
# Terminal 2, from the repository root
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. The comparison proxy defaults to the backend at
`http://127.0.0.1:8000`; set `BACKEND_URL` in `frontend/.env.local` to override it.
The backend reads exported environment variables; simply creating a
`backend/.env` file does not load them.

If you already have `backend/venv`, use its executables instead of creating `.venv`.

## Verify

```bash
cd backend
MODEL_PROVIDER=fake .venv/bin/python -m pytest -q
```

```bash
cd frontend
npm run build
```

## Project map

- `backend/app/compare.py` — evidence evaluation and follow-up questions.
- `backend/app/comparison_schema.py` — validated comparison API contracts.
- `backend/app/server.py` — `/schools`, `/compare`, `/invoke`, and `/health`.
- `frontend/app/page.tsx` — selection, comparison and note-update workflow.
- `frontend/app/api/` — server-side backend proxies.
- `frontend/app/discover/page.tsx` — original discovery UI.
- [Comparison design and API](docs/COMPARISON.md).
- [Original LangGraph architecture](docs/ARCHITECTURE.md).

## Current boundaries

Comparisons and notes are held in page memory and submitted for stateless
evaluation. **Refreshing or leaving the page clears them.** No database or browser
storage is used. Free-text context is displayed for reference; parents explicitly
select the requirements that are evaluated.

The app does not check registration eligibility, geocode a home, retrieve live
school information, verify external links, or predict teachers, peers or future
outcomes. Those are separate data and integration tasks. Production deployment
also needs appropriate access controls and a reviewed data-handling policy.
