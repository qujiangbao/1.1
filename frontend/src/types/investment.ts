export type DataMode = "real" | "demo";

export interface EvidenceItem {
  id: string;
  field: string;
  claim: string;
  value: unknown;
  source_type: string;
  source_title: string;
  source_url?: string | null;
  published_at?: string | null;
  collected_at: string;
  tool: string;
  snapshot_id: string;
  confidence: number;
}

export interface ScoreDimension {
  score: number | null;
  weight: number;
  reason: string;
  evidence_ids: string[];
}

export type AgentRunStatus = "SUCCESS" | "DATA_INSUFFICIENT" | "FAILED";

export interface AgentOutputEnvelope {
  agent: string;
  enterprise_id?: string | null;
  status: AgentRunStatus;
  result: Record<string, unknown>;
  evidence_ids: string[];
  unknown_fields: string[];
  warnings: string[];
  tools_used: string[];
  data_sources: string[];
  run_ref?: string | null;
  execution_time_ms?: number | null;
}

export interface PolicyConditionResult {
  condition_code: string;
  label: string;
  field: string;
  operator: string;
  expected_value: unknown;
  actual_value: unknown;
  mandatory: boolean;
  status:
    | "SATISFIED"
    | "UNSATISFIED"
    | "UNKNOWN"
    | "NEEDS_MANUAL_REVIEW"
    | "NOT_APPLICABLE";
  reason: string;
  source_text?: string | null;
  evidence_ids: string[];
}

export interface PolicyMatch {
  policy_id?: string | null;
  title: string;
  match_type:
    | "RELATED"
    | "POTENTIALLY_ELIGIBLE"
    | "ELIGIBLE"
    | "INELIGIBLE"
    | "UNKNOWN";
  reason: string;
  match_score?: number | null;
  matched_terms: string[];
  source_type?: string;
  source_title?: string | null;
  source_url?: string | null;
  evidence_ids: string[];
  condition_results: PolicyConditionResult[];
}

export interface RecommendationCard {
  enterprise_id: string;
  enterprise_name: string;
  industry_chain_role?: string | null;
  overall_score: number | null;
  confidence: number | null;
  data_status: "READY" | "DATA_INSUFFICIENT";
  score_breakdown: Record<string, ScoreDimension>;
  risk: {
    level: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
    score: number | null;
    reason: string;
    evidence_ids: string[];
  };
  policy_matches: PolicyMatch[];
  recommendation: string;
  next_action: string;
  evidence: EvidenceItem[];
  unknown_fields: string[];
  warnings: string[];
  data_mode: DataMode;
  agent_outputs: Record<string, AgentOutputEnvelope>;
  trace_refs: Record<string, string>;
}

export interface ScenarioCreated {
  scenario_id: string;
  task_id?: string | null;
  stream_url?: string | null;
  status: string;
}

export interface RecommendationResponse {
  scenario_id: string;
  scenario_name: string;
  data_mode: DataMode;
  generated_at: string;
  version: string;
  source_summary: Record<string, unknown>;
  limitations: string[];
  recommendations: RecommendationCard[];
}

export interface InvestmentEvaluationReport {
  report_id: string;
  dataset_id: string;
  generated_at: string;
  scoring_version: string;
  scope: string;
  passed: boolean;
  thresholds: Record<string, number>;
  metrics: {
    dataset_size: number;
    found_count: number;
    source_traceability_rate: number;
    evidence_linkage_rate: number;
    missing_value_integrity_rate: number;
    risk_unknown_integrity_rate: number;
    deterministic_repeat_rate: number;
  };
  cases: Array<Record<string, unknown>>;
}

export interface OfflineLearningReport {
  generated_at: string;
  data_mode: DataMode;
  mode: "OFFLINE_PROPOSAL_ONLY";
  ready: boolean;
  activation_allowed: false;
  thresholds: Record<string, number>;
  sample: {
    impressions: number;
    labeled_feedback: number;
    accepted: number;
    rejected: number;
  };
  baseline_weights: Record<string, number>;
  proposed_weights: Record<string, number> | null;
  dimension_diagnostics: Record<string, unknown>;
  reason: string;
}

export type CandidateStatus =
  | "NEW"
  | "REVIEWED"
  | "CONTACTING"
  | "NEGOTIATING"
  | "REJECTED"
  | "ARCHIVED";

export interface InvestmentCandidate {
  id: string;
  enterprise_id: string;
  enterprise_name: string;
  scenario_id: string;
  industry_chain_role?: string | null;
  overall_score: number | null;
  confidence: number | null;
  score_breakdown: Record<string, ScoreDimension>;
  evidence: EvidenceItem[];
  unknown_fields: string[];
  warnings: string[];
  risk_level: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  risk_summary?: string | null;
  policy_matches: RecommendationCard["policy_matches"];
  recommendation: string;
  next_action?: string | null;
  status: CandidateStatus;
  assignee_id?: string | null;
  source_task_id?: string | null;
  data_mode: DataMode;
  manual_note?: string | null;
  agent_outputs: Record<string, AgentOutputEnvelope>;
  trace_refs: Record<string, string>;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CandidateList {
  items: InvestmentCandidate[];
  total: number;
  limit: number;
  offset: number;
  next_cursor?: string | null;
  data_mode: DataMode;
}
