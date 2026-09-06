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

## Fly.io demo deployment

The branch demo runs at https://school-fit-comparison.fly.dev. To deploy the current
checkout from the repository root with an authenticated Fly.io CLI:

```bash
fly deploy --remote-only --ha=false
fly checks list
```

The Docker image builds the standalone Next.js frontend and runs the backend tests.
Both services run as a non-root user on one 512 MB shared-CPU machine in Singapore;
the backend listens only on loopback. `/api/health` checks both services. No API
keys, database, or volume are needed, and local environment files are excluded
from the remote build. Discovery explicitly uses `MODEL_PROVIDER=fake`.

The frontend uses the supported Next.js 15.5 line. The PostCSS override keeps its
transitive CSS dependency patched; review it when updating Next.js.

The machine stops when idle and wakes on requests, so the first visit can be slower.
This trades availability and cold-start latency for a smaller demo footprint;
Fly.io usage charges still apply. This is a public, fictional-data prototype, not
a production service for sensitive child information. Notes still clear on refresh.

For a separate Fly app, create it with `fly apps create <name> --org <your-org>` and
change `app` in `fly.toml` before deploying. See the
[Fly deployment documentation](https://fly.io/docs/launch/deploy/).

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
