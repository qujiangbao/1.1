import { apiFetch, apiJson, ApiError } from "@/api/fetch";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export interface ParkDocument {
  id: string;
  name: string;
  category: string;
  tags: string[];
  format: string;
  file_size: number;
  page_count: number;
  file_hash: string;
  status: "READY" | "FAILED";
  error?: string | null;
  text_length: number;
  excerpt: string;
  created_by: string;
  created_at: string;
  content_hash?: string;
  duplicate?: boolean;
  duplicate_of?: string;
  structured_enterprises?: number;
  structured_risk_events?: number;
}

export async function listParkDocuments() {
  const payload = await apiJson<{ success: boolean; data: ParkDocument[] }>(`${API}/documents`);
  return payload.data;
}

export async function uploadParkDocument(file: File, category: string, tags: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  form.append("tags", tags);
  const response = await apiFetch(`${API}/documents`, { method: "POST", body: form });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? String((payload as { detail?: unknown }).detail || "")
      : "";
    throw new ApiError(detail || `上传失败（HTTP ${response.status}）`, response.status, payload);
  }
  return (payload as { data: ParkDocument }).data;
}

export async function deleteParkDocument(documentId: string) {
  return apiJson(`${API}/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}
