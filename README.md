# Primary School Ballot — School-Fit Copilot

A starting scaffold for IGNITE 2026 (Software AI track): a LangGraph agent
backend + Next.js frontend that turns a parent's free-text description of
their child into ranked, *explained* primary-school recommendations —
covering SEN/programme fit, commute, admission odds, and community
experience.

- **What & why**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Backend**: [`backend/README.md`](backend/README.md) — LangGraph agent
  graph, runnable/testable with zero API keys (`MODEL_PROVIDER=fake`).
  Tested: `pytest` passes 2/2.
- **Frontend**: [`frontend/README.md`](frontend/README.md) — Next.js chat UI,
  deploys to Vercel. Tested: `npm run build` compiles clean.

## Quickstart (both halves, local)

```bash
# terminal 1 — backend
cd backend
pip install --break-system-packages -r requirements.txt
cp .env.example .env
uvicorn app.server:app --reload

# terminal 2 — frontend
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Then open `http://localhost:3000`.

Everything runs with `MODEL_PROVIDER=fake` (no API keys) — good enough to
see the full pipeline work end-to-end. Switch to `groq` or `bedrock` in
`backend/.env` once you're plugging in the real model from the hackathon
labs (see `backend/README.md`).

## What's real vs. placeholder right now

This is a scaffold, not a finished product — it's built so the *shape* is
right and every piece actually runs, but several pieces are intentionally
stubbed so the whole thing is demoable today:

- `backend/app/data/schools.json` — 5 **fictional** schools. Swap for real data.
- `backend/app/tools/commute.py` — straight-line distance, not real routing.
  Swap for OneMap (Singapore's official geocoding API).
- `backend/app/tools/community.py` — 4 **synthetic**, clearly-labelled
  sample experiences. Read the docstring before adding real ones — this is
  personal data about children (including SEN status), so it needs consent,
  not scraping. See `docs/ARCHITECTURE.md` for the PDPA note.

Everything else (profile extraction, SEN scoring, Bayesian admission odds,
per-school synthesis, the graph wiring, the API, the UI) is real and working.

## Pushing this into the team repo

This folder isn't a git repo yet and hasn't been pushed anywhere. To put it
into `P4pomepeii/Primary-school-Ballot` (currently empty):

```bash
cd primary-school-ballot   # this folder
git init
git add .
git commit -m "Scaffold: LangGraph backend + Next.js frontend for School-Fit Copilot"
git branch -M main
git remote add origin https://github.com/P4pomepeii/Primary-school-Ballot.git
git push -u origin main
```

Run that yourself, signed in as you (or a teammate) — I don't have and
haven't requested any access to your GitHub, and haven't added myself as a
collaborator anywhere.

## Repo layout

```
backend/    LangGraph agent graph + FastAPI server (deploy target: AWS Bedrock AgentCore)
frontend/   Next.js chat UI (deploy target: Vercel)
docs/       architecture write-up
```
