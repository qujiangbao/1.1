import { apiJson } from "@/api/fetch";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export type TicketStatus = "OPEN" | "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED";
export type TicketPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface ServiceTicket {
  id: string;
  enterprise_id?: string | null;
  enterprise_name?: string | null;
  subject: string;
  description: string;
  category: string;
  priority: TicketPriority;
  status: TicketStatus;
  assignee_id?: string | null;
  due_at?: string | null;
  resolution?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export async function listServiceTickets(status?: TicketStatus, query = "") {
  const params = new URLSearchParams({ limit: "500" });
  if (status) params.set("status", status);
  if (query.trim()) params.set("q", query.trim());
  const payload = await apiJson<{ success: boolean; data: ServiceTicket[] }>(
    `${API}/service-tickets?${params.toString()}`,
  );
  return payload.data;
}

export async function createServiceTicket(input: {
  enterprise_id?: string;
  enterprise_name?: string;
  subject: string;
  description: string;
  category: string;
  priority: TicketPriority;
  assignee_id?: string;
  due_at?: string;
}) {
  const payload = await apiJson<{ success: boolean; data: ServiceTicket }>(
    `${API}/service-tickets`,
    { method: "POST", body: JSON.stringify(input) },
  );
  return payload.data;
}

export async function updateServiceTicket(
  ticketId: string,
  changes: Partial<Pick<ServiceTicket, "status" | "priority" | "assignee_id" | "due_at" | "resolution">>,
) {
  const payload = await apiJson<{ success: boolean; data: ServiceTicket }>(
    `${API}/service-tickets/${encodeURIComponent(ticketId)}`,
    { method: "PATCH", body: JSON.stringify(changes) },
  );
  return payload.data;
}
