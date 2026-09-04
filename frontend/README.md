# frontend — School-Fit Copilot (Next.js)

Thin UI. All the intelligence lives in `../backend`. This app just:

1. Collects the parent's free-text description of their child (`app/page.tsx`).
2. Sends it to `app/api/chat/route.ts`, a server-side proxy that calls the
   backend's `POST /invoke`.
3. Renders the returned `SchoolFitResult[]` as ranked cards with expandable
   evidence.

## Run locally

```bash
npm install
cp .env.example .env.local   # BACKEND_URL defaults to http://localhost:8000
npm run dev
```

Needs the backend running too — see `../backend/README.md` (or just:
`cd ../backend && MODEL_PROVIDER=fake uvicorn app.server:app --reload`).

## Deploy to Vercel

1. Push this repo to GitHub (see the root README for the exact commands).
2. Import the repo in Vercel, set the **root directory** to `frontend/`.
3. Add an environment variable `BACKEND_URL` pointing at wherever the
   LangGraph backend ends up running (Bedrock AgentCore endpoint, or any
   other host running `backend/app/server.py`).
4. Deploy. The API route (`app/api/chat/route.ts`) runs as a Vercel
   serverless function, so your backend credentials never reach the browser.

## Files

- `app/page.tsx` — the chat/results UI (client component).
- `app/api/chat/route.ts` — server-side proxy to the backend.
- `app/types.ts` — TypeScript mirror of `backend/app/schema.py`. Keep these
  two in sync by hand for now.
- `app/layout.tsx` — root layout + page metadata.
