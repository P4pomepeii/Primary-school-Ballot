// Mirrors backend/app/schema.py — keep these two in sync by hand for now;
// worth generating from the Pydantic schema once the shape stabilizes.

export interface SchoolFitEvidence {
  school_id: string;
  source: "sen_support" | "commute" | "admission_odds" | "community";
  summary: string;
  concern?: string | null;
  score_0_to_1: number;
  citation?: string | null;
}

export interface SchoolFitResult {
  school_id: string;
  school_name: string;
  fit_summary: string;
  concerns: string[];
  distance_km?: number | null;
  commute_minutes?: number | null;
  admission_odds_pct?: number | null;
  evidence: SchoolFitEvidence[];
}
