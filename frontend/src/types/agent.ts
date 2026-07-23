export interface ChatResponse {
  task_id: string;
  conversation_id: string;
  status: string;
  response?: string;
  agents_used: string[];
  trace_id?: string;
  execution_time_ms?: number;
}

export interface TraceData {
  trace_id: string;
  task_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  execution_time_ms: number;
  steps: TraceStep[];
  nodes: TraceNode[];
  edges: TraceEdge[];
}

export interface TraceStep {
  step: number;
  type: string;
  agent: string;
  action: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  timestamp: string;
  duration_ms: number;
}

export interface TraceNode {
  id: string;
  label: string;
  type: string;
}

export interface TraceEdge {
  from: string;
  to: string;
}

export interface DashboardData {
  park_overview: Record<string, unknown>;
  investment: Record<string, unknown>;
  risk: Record<string, unknown>;
  ai_operations: Record<string, unknown>;
}

export interface AgentStatus {
  name: string;
  display: string;
  capabilities: string[];
}
