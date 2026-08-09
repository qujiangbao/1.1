import type { DataMode } from "@/types/investment";

export interface ManagedPolicyCondition {
  condition_code: string;
  label: string;
  field: string;
  operator:
    | "EXISTS"
    | "EQ"
    | "NE"
    | "IN"
    | "CONTAINS"
    | "GTE"
    | "GT"
    | "LTE"
    | "LT";
  expected_value: unknown;
  mandatory: boolean;
  review_status: "DRAFT" | "REVIEWED";
  source_text?: string | null;
}

export interface ManagedPolicy {
  policy_id: string;
  title: string;
  level?: string | null;
  department?: string | null;
  category?: string | null;
  industry_scope?: string[] | null;
  region_scope?: string[] | null;
  publish_date?: string | null;
  expire_date?: string | null;
  status?: string | null;
  source?: string | null;
  eligibility_conditions: ManagedPolicyCondition[];
  conditions_reviewed_at?: string | null;
  conditions_reviewed_by?: string | null;
}

export type PolicyCandidateMatchType =
  | "ELIGIBLE"
  | "POTENTIALLY_ELIGIBLE"
  | "INELIGIBLE"
  | "RELATED"
  | "UNKNOWN";

export interface PolicyCandidateConditionResult {
  condition_code: string;
  label: string;
  field: string;
  operator: string;
  expected_value: unknown;
  actual_value?: unknown;
  status:
    | "SATISFIED"
    | "UNSATISFIED"
    | "UNKNOWN"
    | "NEEDS_MANUAL_REVIEW"
    | "NOT_APPLICABLE";
  mandatory: boolean;
  reason: string;
  source_text?: string | null;
}

export interface PolicyCandidateEligibilityItem {
  candidate_id: string;
  enterprise_id: string;
  enterprise_name: string;
  candidate_status: string;
  match_type: PolicyCandidateMatchType;
  reason: string;
  match_score?: number | null;
  matched_terms: string[];
  condition_results: PolicyCandidateConditionResult[];
  evaluated_at?: string | null;
}

export interface PolicyCandidateEligibilityReport {
  policy_id: string;
  policy_title: string;
  data_mode: DataMode;
  scope: "investment_candidate_pool";
  scope_candidate_count: number;
  relevant_candidate_count: number;
  eligible_count: number;
  potential_count: number;
  ineligible_count: number;
  condition_count: number;
  reviewed_condition_count: number;
  conditions_origin?: string | null;
  items: PolicyCandidateEligibilityItem[];
}

export interface ManagedUser {
  user_id: string;
  username: string;
  display_name?: string | null;
  role: string;
  park_id?: string | null;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export type PolicyCrawlerAccessStatus =
  | "OWNER"
  | "APPROVED"
  | "PENDING"
  | "NOT_REQUESTED"
  | "REVOKED"
  | "UNAVAILABLE"
  | "FORBIDDEN";

export interface PolicyCrawlerAccessState {
  allowed: boolean;
  is_root_admin: boolean;
  status: PolicyCrawlerAccessStatus;
  reason: string;
  request_id?: string;
}

export interface PolicyCrawlerAccessRequest {
  request_id: string;
  requester_id: string;
  username: string;
  display_name?: string | null;
  reason?: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
  decided_by?: string | null;
  decision_note?: string | null;
  requested_at: string;
  decided_at?: string | null;
}

export interface PolicyCrawlerGrant {
  user_id: string;
  username: string;
  display_name?: string | null;
  status: "APPROVED" | "REVOKED";
  approved_by: string;
  approved_at: string;
  revoked_by?: string | null;
  revoked_at?: string | null;
}

export type PolicyCrawlRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "PARTIAL"
  | "FAILED";

export interface PolicyCrawlRun {
  run_id: string;
  requested_by: string;
  status: PolicyCrawlRunStatus;
  pages: number;
  workers: number;
  force: boolean;
  stats: Record<string, unknown>;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export type FollowUpTaskStatus =
  | "TODO"
  | "IN_PROGRESS"
  | "DONE"
  | "CANCELLED";

export interface FollowUpTask {
  id: string;
  candidate_id: string;
  title: string;
  description?: string | null;
  owner_id: string;
  due_at?: string | null;
  priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  status: FollowUpTaskStatus;
  completion_note?: string | null;
  data_mode: DataMode;
  created_by: string;
  created_at: string;
  updated_at: string;
}
