from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# === Agent Chat ===
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=8000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    stream: bool = False


class ChatResponse(BaseModel):
    task_id: str
    conversation_id: str
    status: str
    response: Optional[str] = None
    agents_used: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
    execution_time_ms: Optional[int] = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


# === Task Message (Agent 间通信) ===
class TaskMessage(BaseModel):
    task_id: str
    from_agent: str
    to_agent: str
    intent: str
    priority: str = "medium"
    input: Dict[str, Any] = Field(default_factory=dict)
    expected_output: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    task_id: str
    agent: str
    status: str  # success / partial / failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


# === Agent Capability ===
class AgentCapability(BaseModel):
    agent_name: str
    display_name: str
    capabilities: List[str]
    input_schema: Dict[str, str] = Field(default_factory=dict)
    output_schema: Dict[str, str] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    consumers: List[str] = Field(default_factory=list)


# === Trace ===
class TraceStep(BaseModel):
    step: int
    type: str
    agent: str
    action: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    duration_ms: int = 0


class TraceResponse(BaseModel):
    trace_id: str
    task_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    execution_time_ms: int = 0
    steps: List[TraceStep] = Field(default_factory=list)
    nodes: List[Dict] = Field(default_factory=list)
    edges: List[Dict] = Field(default_factory=list)
    task_plan: List[Dict] = Field(default_factory=list)


# === Dashboard ===
class DashboardOverview(BaseModel):
    park_overview: Dict[str, Any]
    investment: Dict[str, Any]
    risk: Dict[str, Any]
    ai_operations: Dict[str, Any]


# === Common ===
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, str]] = None
