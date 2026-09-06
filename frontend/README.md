# frontend — School-Fit Copilot (Next.js)

Thin UI. All the intelligence lives in `../backend`. This app just:

1. Loads `/api/schools` and lets parents select two schools and their requirements.
2. Sends a structured request to `/api/compare`, which proxies to FastAPI.
3. Shows evidence and unresolved questions side by side, without ranking schools.
4. Lets parents record or remove information and see what changed.

Notes are held only in page memory; reloading or navigating away clears them.
Editing the meaning of a requirement excludes its previous notes, with a warning
before submission. Changing only its importance retains those notes.

The original chat/results UI remains at `/discover`, using `/api/chat` and the
legacy backend's `/invoke` endpoint. See [comparison design](../docs/COMPARISON.md).

## Run locally

```bash
npm install
cp .env.example .env.local   # BACKEND_URL defaults to http://localhost:8000
npm run dev
```

Needs the backend running too — see `../backend/README.md` (or just:
`cd ../backend && MODEL_PROVIDER=fake .venv/bin/uvicorn app.server:app --reload`).

## Deploy to Vercel

1. Push the repository to your GitHub account.
2. Import the repo in Vercel, set the **root directory** to `frontend/`.
3. Set `BACKEND_URL` to a deployment of the FastAPI application in
   `backend/app/server.py`. It must expose `/schools`, `/compare` and `/invoke`;
   an AgentCore graph endpoint alone does not supply the new comparison routes.
4. Deploy. The API routes run server-side, so the backend address stays out of
   the browser bundle. Backend authentication would need to be added to the proxies.

## Files

- `app/page.tsx` — the two-school comparison and note-update workflow.
- `app/comparison-types.ts` — TypeScript comparison API contract.
- `app/globals.css` — responsive comparison styles and shared theme.
- `app/api/compare/route.ts`, `app/api/schools/route.ts` — comparison proxies.
- `app/discover/page.tsx` — the original discovery UI.
- `app/api/chat/route.ts` — server-side proxy to the backend.
- `app/types.ts` — TypeScript mirror of `backend/app/schema.py`. Keep these
  two in sync by hand for now.
- `app/layout.tsx` — root layout + page metadata.
