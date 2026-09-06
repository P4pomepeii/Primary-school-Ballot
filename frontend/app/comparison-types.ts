// Mirrors backend/app/comparison_schema.py. The comparison has no fit score or winner.
export type Topic = "quiet_space" | "learning_support" | "student_care" | "commute" | "workload" | "social_inclusion" | "cca" | "custom";
export type Priority = "must_have" | "preference";
export type EvidenceStatus = "supported" | "not_met" | "unknown" | "conflicting";
export type Outcome = "supports" | "does_not_support" | "unclear";
export type ObservationSource = "school_response" | "published_information" | "parent_experience" | "family_observation";

export interface School {
  school_id: string;
  school_name: string;
  is_demo: boolean;
}
export interface TopicOption {
  id: Topic;
  label: string;
  description: string;
  question: string;
}
export interface Catalogue {
  schools: School[];
  topics: TopicOption[];
  notice: string;
}
export interface Requirement {
  id: string;
  topic: Topic;
  priority: Priority;
  details: string;
  max_minutes: number | null;
}
export interface Observation {
  id: string;
  school_id: string;
  requirement_id: string;
  source_type: ObservationSource;
  source_label: string;
  source_url: string | null;
  observed_on: string;
  summary: string;
  outcome: Outcome;
  commute_minutes: number | null;
}
export interface ComparisonRequest {
  school_ids: [string, string];
  school_names?: [string, string];
  context: string;
  requirements: Requirement[];
  observations: Observation[];
}
export interface ComparisonEvidence {
  id: string;
  source_type: ObservationSource | "demo";
  source_label: string;
  source_url: string | null;
  observed_on: string | null;
  summary: string;
  outcome: Outcome;
  commute_minutes: number | null;
  is_demo: boolean;
}
export interface ComparisonCell {
  school_id: string;
  status: EvidenceStatus;
  explanation: string;
  evidence: ComparisonEvidence[];
}
export interface ComparisonRow {
  requirement: Requirement;
  label: string;
  cells: ComparisonCell[];
}
export interface ComparisonResponse {
  notice: string;
  context: string;
  schools: School[];
  rows: ComparisonRow[];
  assessments: {
    school_id: string;
    state: "needs_confirmation" | "unmet_requirement" | "requirements_supported" | "preferences_only";
    summary: string;
    supported_required: number;
    total_required: number;
  }[];
  questions: {
    id: string;
    school_id: string;
    requirement_id: string;
    priority: Priority;
    question: string;
    reason: string;
  }[];
}
