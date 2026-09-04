"use client";

import { useState } from "react";
import type { SchoolFitResult } from "@/app/types";

const PLACEHOLDER =
  "e.g. My daughter has ADHD and gets overwhelmed by loud, crowded spaces. She loves swimming and art. We're at Bishan, Phase 2B, and I'd prefer under 20 minutes commute. My husband's an alumnus of a school nearby too.";

const SOURCE_LABEL: Record<SchoolFitResult["evidence"][number]["source"], string> = {
  sen_support: "SEN / learning support",
  commute: "Commute",
  admission_odds: "Admission odds",
  community: "Community experience",
};

export default function HomePage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SchoolFitResult[] | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error ?? `Request failed (${res.status})`);
      }
      setResults(data.results ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 20px 96px" }}>
      <header style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, marginBottom: 6 }}>School-Fit Copilot</h1>
        <p style={{ color: "#555", fontSize: 15, lineHeight: 1.5 }}>
          Describe your child in your own words — needs, interests, home area, ballot
          phase. We&apos;ll explain <em>why</em> each school fits, not just rank them.
        </p>
      </header>

      <form onSubmit={handleSubmit} style={{ marginBottom: 32 }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={PLACEHOLDER}
          rows={6}
          style={{
            width: "100%",
            padding: 14,
            fontSize: 15,
            fontFamily: "inherit",
            border: "1px solid #d8d6d0",
            borderRadius: 10,
            resize: "vertical",
            boxSizing: "border-box",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            marginTop: 12,
            padding: "10px 22px",
            fontSize: 15,
            fontWeight: 600,
            color: "#fff",
            background: loading ? "#999" : "#1a1a1a",
            border: "none",
            borderRadius: 8,
            cursor: loading ? "default" : "pointer",
          }}
        >
          {loading ? "Thinking…" : "Find schools"}
        </button>
      </form>

      {error && (
        <div
          style={{
            padding: 14,
            background: "#fdecea",
            border: "1px solid #f3c2bc",
            borderRadius: 8,
            color: "#8a2f26",
            marginBottom: 24,
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {results && results.length === 0 && !error && (
        <p style={{ color: "#666" }}>No matching schools found for that profile.</p>
      )}

      {results && results.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {results.map((r, i) => (
            <article
              key={r.school_id}
              style={{
                border: "1px solid #e2e0da",
                borderRadius: 12,
                padding: 20,
                background: "#fff",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <h2 style={{ fontSize: 18, margin: 0 }}>
                  {i + 1}. {r.school_name}
                </h2>
                {r.admission_odds_pct != null && (
                  <span style={{ fontSize: 13, color: "#666" }}>
                    ~{r.admission_odds_pct}% admission odds
                  </span>
                )}
              </div>

              <p style={{ fontSize: 14, color: "#666", marginTop: 4 }}>
                {r.distance_km != null && `${r.distance_km.toFixed(1)} km`}
                {r.distance_km != null && r.commute_minutes != null && " · "}
                {r.commute_minutes != null && `~${r.commute_minutes} min commute`}
              </p>

              <p style={{ fontSize: 15, lineHeight: 1.55, marginTop: 10 }}>{r.fit_summary}</p>

              {r.concerns.length > 0 && (
                <div style={{ marginTop: 10, fontSize: 14, color: "#8a5a00" }}>
                  <strong>Worth knowing:</strong> {r.concerns.join(" · ")}
                </div>
              )}

              <details style={{ marginTop: 12 }}>
                <summary style={{ cursor: "pointer", fontSize: 13, color: "#555" }}>
                  Show evidence ({r.evidence.length})
                </summary>
                <ul style={{ marginTop: 8, paddingLeft: 18, fontSize: 13, color: "#444" }}>
                  {r.evidence.map((ev, j) => (
                    <li key={j} style={{ marginBottom: 6 }}>
                      <strong>{SOURCE_LABEL[ev.source]}:</strong> {ev.summary}
                      {ev.citation && <span style={{ color: "#888" }}> ({ev.citation})</span>}
                    </li>
                  ))}
                </ul>
              </details>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
