// Server-side proxy to the LangGraph backend.
//
// Why this exists instead of calling the backend directly from the browser:
// - Keeps BACKEND_URL (and, once deployed, any AWS Bedrock AgentCore auth)
//   server-side only — never shipped to the client bundle.
// - Gives us one place to add auth/rate-limiting later without touching the UI.
//
// Local dev: BACKEND_URL defaults to the FastAPI dev server (uvicorn app.server:app).
// Production: point BACKEND_URL at the deployed AgentCore/FastAPI endpoint via
// a Vercel environment variable.

import { NextRequest, NextResponse } from "next/server";
import type { SchoolFitResult } from "@/app/types";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  let message: string;
  try {
    const body = await req.json();
    message = typeof body?.message === "string" ? body.message.trim() : "";
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  if (!message) {
    return NextResponse.json({ error: "message is required." }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${BACKEND_URL}/invoke`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      // This call can take a few seconds — four tool nodes run in parallel
      // per candidate school, then one LLM synthesis pass per school.
      cache: "no-store",
    });

    if (!upstream.ok) {
      const text = await upstream.text().catch(() => "");
      return NextResponse.json(
        { error: `Backend returned ${upstream.status}: ${text || upstream.statusText}` },
        { status: 502 }
      );
    }

    const data: { results: SchoolFitResult[] } = await upstream.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      {
        error:
          "Could not reach the backend. Is it running? (local dev: `uvicorn app.server:app --reload` in backend/, with BACKEND_URL set to its address).",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 502 }
    );
  }
}
