import { NextRequest, NextResponse } from "next/server";
import { comparisonProxy } from "../comparison-proxy";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Please send a valid comparison request." }, { status: 400 });
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ error: "Please send your schools and requirements." }, { status: 400 });
  }
  return comparisonProxy("/compare", body);
}
