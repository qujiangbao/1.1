import { ApiError, apiFetch, apiJson } from "@/api/fetch";
import type {
  CandidateList,
  CandidateStatus,
  DataMode,
  InvestmentEvaluationReport,
  InvestmentCandidate,
  OfflineLearningReport,
  RecommendationCard,
  RecommendationResponse,
  ScenarioCreated,
} from "@/types/investment";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export interface ScenarioInput {
  name: string;
  industry: string;
  target_chain_roles: string[];
  location_preference?: string;
  limit: number;
  data_mode: DataMode;
  weights?: Record<string, number>;
}

export async function createScenario(input: ScenarioInput) {
  return apiJson<ScenarioCreated>(`${API}/investment/scenarios`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getRecommendations(scenarioId: string) {
  const payload = await apiJson<{
    success: boolean;
    data: RecommendationResponse;
  }>(`${API}/investment/scenarios/${encodeURIComponent(scenarioId)}/recommendations`);
  return payload.data;
}

export async function getLatestEvaluation() {
  const payload = await apiJson<{
    success: boolean;
    data: InvestmentEvaluationReport;
  }>(`${API}/investment/evaluation/latest`);
  return payload.data;
}

export async function downloadScenarioPdf(scenarioId: string) {
  const response = await apiFetch(
    `${API}/investment/scenarios/${encodeURIComponent(scenarioId)}/report.pdf`,
  );
  if (!response.ok) {
    throw new ApiError(`PDF 导出失败（HTTP ${response.status}）`, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `investment-report-${scenarioId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function recordRecommendationExposure(
  scenarioId: string,
  dataMode: DataMode,
  eventType: "IMPRESSION" | "SELECT",
  items: Array<{
    enterprise_id: string;
    position: number;
    score: number | null;
  }>,
) {
  return apiJson(
    `${API}/investment/scenarios/${encodeURIComponent(scenarioId)}/exposures`,
    {
      method: "POST",
      body: JSON.stringify({
        event_type: eventType,
        data_mode: dataMode,
        items,
        context: { surface: "investment_dashboard" },
      }),
    },
  );
}

export async function getOfflineLearningReport(dataMode: DataMode) {
  const payload = await apiJson<{
    success: boolean;
    data: OfflineLearningReport;
  }>(`${API}/investment/learning/offline-report?data_mode=${dataMode}`);
  return payload.data;
}

export async function addCandidate(
  scenarioId: string,
  recommendation: RecommendationCard,
  dataMode: DataMode,
) {
  const payload = await apiJson<{
    success: boolean;
    created: boolean;
    data: InvestmentCandidate;
  }>(`${API}/investment/candidates`, {
    method: "POST",
    body: JSON.stringify({
      scenario_id: scenarioId,
      recommendation,
      data_mode: dataMode,
    }),
  });
  return payload;
}

export async function getCandidates(
  dataMode: DataMode,
  status?: CandidateStatus,
) {
  const params = new URLSearchParams({ data_mode: dataMode, limit: "100" });
  if (status) params.set("status", status);
  const payload = await apiJson<{ success: boolean; data: CandidateList }>(
    `${API}/investment/candidates?${params.toString()}`,
  );
  return payload.data;
}

export async function patchCandidate(
  candidateId: string,
  changes: {
    status?: CandidateStatus;
    assignee_id?: string | null;
    next_action?: string | null;
    manual_note?: string | null;
  },
) {
  const payload = await apiJson<{
    success: boolean;
    data: InvestmentCandidate;
  }>(`${API}/investment/candidates/${encodeURIComponent(candidateId)}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
  return payload.data;
}

export async function submitCandidateFeedback(
  candidateId: string,
  feedback: {
    decision: "ACCEPT" | "REJECT" | "NEED_MORE_EVIDENCE" | "DEFER";
    reason_code: string;
    comment?: string;
  },
) {
  return apiJson(`${API}/investment/candidates/${encodeURIComponent(candidateId)}/feedback`, {
    method: "POST",
    body: JSON.stringify(feedback),
  });
}
