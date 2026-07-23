"""Enterprise Service Agent Nodes"""
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from app.tools.gateway import get_tool_gateway

tg = get_tool_gateway()

SERVICE_CATALOG = {
    "policy_service":     {"name": "政策服务", "agent": "PolicyAgent"},
    "talent_service":     {"name": "人才服务", "agent": None},
    "finance_service":    {"name": "金融服务", "agent": None},
    "technology_service": {"name": "技术服务", "agent": "IndustryAgent"},
    "market_service":     {"name": "市场服务", "agent": "IndustryAgent"},
    "space_service":      {"name": "空间服务", "agent": None},
    "government_service": {"name": "政务服务", "agent": "PolicyAgent"},
    "growth_service":     {"name": "成长服务", "agent": None},
}


class ServiceState(TypedDict):
    task_id: str
    input: Dict[str, Any]
    enterprise_id: str
    request: str
    priority: str
    intent: str
    service_category: str
    sub_services: List[str]
    ticket_id: Optional[str]
    lifecycle_stage: str
    agent_results: Dict[str, Dict]
    final_response: Optional[Dict]
    status: str
    tools_used: List[str]


def intent_analyzer(state: ServiceState) -> ServiceState:
    inp = state.get("input", {})
    state["request"] = inp.get("request", "")
    state["enterprise_id"] = inp.get("enterprise_id", "")
    state["intent"] = "service_request"
    state["service_category"] = "policy_service"
    state["sub_services"] = ["policy_service"]
    state["lifecycle_stage"] = "growing"
    state["tools_used"] = []
    state["status"] = "ticketing"
    return state


def ticket_manager(state: ServiceState) -> ServiceState:
    state["ticket_id"] = f"ST-{state['task_id'][:8]}"
    state["status"] = "processing"
    return state


def workflow_engine(state: ServiceState) -> ServiceState:
    results = {}
    for svc in state.get("sub_services", []):
        cat = SERVICE_CATALOG.get(svc, {})
        results[svc] = {
            "service": cat.get("name", svc),
            "agent": cat.get("agent"),
            "status": "completed",
            "result": {"summary": f"{cat.get('name', svc)}处理完成"},
        }
    state["agent_results"] = results
    state["status"] = "aggregating"
    return state


def result_aggregator(state: ServiceState) -> ServiceState:
    state["final_response"] = {
        "ticket_id": state["ticket_id"],
        "service_category": state["service_category"],
        "results": state["agent_results"],
        "next_steps": ["政策申报材料准备", "关注审批进度"],
    }
    state["status"] = "done"
    return state


def build_service_graph():
    w = StateGraph(ServiceState)
    for n, f in [("intent_analyzer", intent_analyzer), ("ticket", ticket_manager),
                  ("workflow", workflow_engine), ("aggregator", result_aggregator)]:
        w.add_node(n, f)
    w.set_entry_point("intent_analyzer")
    for a, b in [("intent_analyzer","ticket"),("ticket","workflow"),("workflow","aggregator")]:
        w.add_edge(a, b)
    w.add_edge("aggregator", END)
    return w.compile()

_sg = None
def get_service_graph():
    global _sg
    if _sg is None: _sg = build_service_graph()
    return _sg
