import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Report ready only when both the public frontend and private backend respond.
export async function GET() {
  const base = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  let ready = false;
  try {
    const response = await fetch(`${base}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2000),
    });
    ready = response.ok && (await response.json()).status === "ok";
  } catch {
    // Do not disclose upstream URLs or error details in a public health check.
  }
  return NextResponse.json({ status: ready ? "ok" : "unavailable" }, {
    status: ready ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
