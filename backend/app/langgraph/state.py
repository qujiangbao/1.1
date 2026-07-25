"""Supervisor LangGraph State Schema"""
from typing import TypedDict, List, Optional, Dict, Any, Annotated
from langgraph.graph.message import add_messages


class TaskNode(TypedDict):
    task_id: str
    agent: str
    intent: str
    input: Dict[str, Any]
    expected_output: List[str]
    dependencies: List[str]
    priority: str
    status: str  # pending / running / completed / failed


class AgentResult(TypedDict):
    task_id: str
    agent: str
    status: str
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    trace: Optional[Dict[str, Any]]
    execution_time_ms: int


class TraceStep(TypedDict):
    step: int
    type: str
    agent: str
    action: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    timestamp: str
    duration_ms: int


class SupervisorState(TypedDict):
    # User context
    user_id: str
    conversation_id: str
    park_id: Optional[str]
    user_role: str

    # Messages
    messages: Annotated[List[Dict], add_messages]
    user_query: str

    # Intent
    intent: Optional[str]
    intents: Optional[List[str]]
    entities: Optional[Dict[str, Any]]
    confidence: Optional[float]

    # Task planning
    task_plan: Optional[List[TaskNode]]
    current_task_index: Optional[int]

    # Agent routing
    current_agent: Optional[str]
    agent_input: Optional[Dict[str, Any]]
    agent_results: Dict[str, AgentResult]

    # Status
    status: str  # idle / planning / running / completed / failed
    error_count: int
    retry_count: int

    # Result
    aggregated_result: Optional[str]
    final_response: Optional[str]

    # Trace
    trace_id: str
    trace_steps: List[TraceStep]

    # P2: Conversation history injected by API layer
    history_messages: Optional[List[Dict]]

    # Timing
    started_at: str
    completed_at: Optional[str]
