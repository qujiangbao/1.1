import { apiJson } from "@/api/fetch";
import type { DataMode } from "@/types/investment";
import type {
  FollowUpTask,
  FollowUpTaskStatus,
  ManagedPolicy,
  ManagedPolicyCondition,
  PolicyCandidateEligibilityReport,
  ManagedUser,
  PolicyCrawlerAccessState,
  PolicyCrawlerAccessRequest,
  PolicyCrawlerGrant,
  PolicyCrawlRun,
} from "@/types/management";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export async function getManagedPolicies(query = "") {
  const params = new URLSearchParams({ limit: "500" });
  if (query.trim()) params.set("q", query.trim());
  const payload = await apiJson<{
    success: boolean;
    data: { items: ManagedPolicy[]; total: number };
  }>(`${API}/policy-management/policies?${params.toString()}`);
  return payload.data;
}

export async function getPolicyCandidateEligibility(policyId: string) {
  const payload = await apiJson<{
    success: boolean;
    data: PolicyCandidateEligibilityReport;
  }>(
    `${API}/policy-management/policies/${encodeURIComponent(policyId)}/candidate-eligibility?data_mode=real`,
  );
  return payload.data;
}

export async function savePolicyConditions(
  policyId: string,
  conditions: ManagedPolicyCondition[],
) {
  const payload = await apiJson<{ success: boolean; data: ManagedPolicy }>(
    `${API}/policy-management/policies/${encodeURIComponent(policyId)}/conditions`,
    {
      method: "PATCH",
      body: JSON.stringify({ conditions }),
    },
  );
  return payload.data;
}

export async function getManagedUsers() {
  const payload = await apiJson<{ users: ManagedUser[] }>(`${API}/admin/users`);
  return payload.users;
}

export async function createManagedUser(input: {
  username: string;
  password: string;
  display_name?: string;
  role: string;
  park_id?: string;
}) {
  return apiJson(`${API}/admin/users`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateManagedUser(
  userId: string,
  changes: Partial<
    Pick<
      ManagedUser,
      "username" | "display_name" | "role" | "park_id" | "is_active"
    >
  > & { password?: string },
) {
  return apiJson(`${API}/admin/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export async function deleteManagedUser(userId: string) {
  return apiJson<{ ok: boolean; deleted_user_id: string }>(
    `${API}/admin/users/${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
}

export async function getPolicyCrawlerAccess() {
  const payload = await apiJson<{ success: boolean; data: PolicyCrawlerAccessState }>(
    `${API}/policy-crawler/access`,
  );
  return payload.data;
}

export async function requestPolicyCrawlerAccess(reason: string) {
  return apiJson(`${API}/policy-crawler/access/requests`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function getPolicyCrawlerAccessRequests() {
  const payload = await apiJson<{
    success: boolean;
    data: PolicyCrawlerAccessRequest[];
  }>(`${API}/policy-crawler/access/requests`);
  return payload.data;
}

export async function decidePolicyCrawlerAccess(
  requestId: string,
  decision: "APPROVED" | "REJECTED",
  note?: string,
) {
  return apiJson(`${API}/policy-crawler/access/requests/${encodeURIComponent(requestId)}`, {
    method: "PATCH",
    body: JSON.stringify({ decision, note }),
  });
}

export async function getPolicyCrawlerGrants() {
  const payload = await apiJson<{
    success: boolean;
    data: PolicyCrawlerGrant[];
  }>(`${API}/policy-crawler/access/grants`);
  return payload.data;
}

export async function revokePolicyCrawlerGrant(userId: string) {
  return apiJson(`${API}/policy-crawler/access/grants/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
}

export async function createPolicyCrawlRun(input: {
  pages: number;
  workers: number;
  force: boolean;
}) {
  const payload = await apiJson<{ success: boolean; data: PolicyCrawlRun }>(
    `${API}/policy-crawler/runs`,
    { method: "POST", body: JSON.stringify(input) },
  );
  return payload.data;
}

export async function getPolicyCrawlRuns() {
  const payload = await apiJson<{ success: boolean; data: PolicyCrawlRun[] }>(
    `${API}/policy-crawler/runs?limit=50`,
  );
  return payload.data;
}

export async function getFollowUpTasks(
  dataMode: DataMode,
  status?: FollowUpTaskStatus,
) {
  const params = new URLSearchParams({ data_mode: dataMode, limit: "500" });
  if (status) params.set("status", status);
  const payload = await apiJson<{ success: boolean; data: FollowUpTask[] }>(
    `${API}/investment/follow-up-tasks?${params.toString()}`,
  );
  return payload.data;
}

export async function createFollowUpTask(input: {
  candidate_id: string;
  title: string;
  description?: string;
  owner_id: string;
  due_at?: string;
  priority: FollowUpTask["priority"];
  data_mode: DataMode;
}) {
  const payload = await apiJson<{ success: boolean; data: FollowUpTask }>(
    `${API}/investment/follow-up-tasks`,
    { method: "POST", body: JSON.stringify(input) },
  );
  return payload.data;
}

export async function updateFollowUpTask(
  taskId: string,
  changes: {
    status?: FollowUpTaskStatus;
    completion_note?: string;
    owner_id?: string;
    due_at?: string | null;
    priority?: FollowUpTask["priority"];
  },
) {
  const payload = await apiJson<{ success: boolean; data: FollowUpTask }>(
    `${API}/investment/follow-up-tasks/${encodeURIComponent(taskId)}`,
    { method: "PATCH", body: JSON.stringify(changes) },
  );
  return payload.data;
}
