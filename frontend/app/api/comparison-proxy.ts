import { NextResponse } from "next/server";

// Only the two fixed comparison endpoints are exposed; browser input cannot choose a host.
export async function comparisonProxy(path: "/schools" | "/compare", body?: unknown) {
  const base = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  try {
    const upstream = await fetch(`${base}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(75000),
    });
    const data = await upstream.json();
    if (!upstream.ok) {
      // Do not relay validation input values, tracebacks, or internal upstream errors.
      const issues = Array.isArray(data.detail)
        ? data.detail.map((issue: { msg?: unknown }) => typeof issue.msg === "string" ? issue.msg : "Check your input.").slice(0, 5)
        : [];
      const error = upstream.status === 422
        ? (issues.join(" ") || (typeof data.detail === "string" ? data.detail : "Please check your schools, requirements and notes."))
        : "The comparison service could not complete the request. Please try again.";
      return NextResponse.json({ error }, {
        status: upstream.status === 422 ? 422 : 502,
        headers: { "Cache-Control": "no-store" },
      });
    }
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "The comparison service is unavailable. Please try again shortly." }, {
      status: 502, headers: { "Cache-Control": "no-store" },
    });
  }
}
