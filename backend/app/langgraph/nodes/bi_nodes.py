"""BI Agent Nodes"""
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END


class BIState(TypedDict):
    task_id: str
    intent: str
    input: Dict[str, Any]
    dashboard_type: str
    topic: Optional[str]
    kpi_result: Optional[Dict]
    dashboard_result: Optional[Dict]
    insight_result: Optional[Dict]
    status: str


def query_router(state: BIState) -> BIState:
    inp = state.get("input", {})
    state["intent"] = inp.get("intent", "dashboard_kpi")
    state["dashboard_type"] = inp.get("dashboard_type", "overview")
    state["status"] = "computing"
    return state


def kpi_calculator(state: BIState) -> BIState:
    state["kpi_result"] = {
        "park_overview": {"total_enterprises": 12580, "growth_rate": "3.2%"},
        "investment": {"opportunities": 230, "signed": 12, "conversion_rate": "5.2%"},
        "risk": {"high_risk": 20, "medium_risk": 80, "low_risk": 500},
        "ai_operations": {"agent_calls": 1520, "success_rate": "97.4%"},
    }
    state["status"] = "building_dashboard"
    return state


def dashboard_builder(state: BIState) -> BIState:
    state["dashboard_result"] = {
        "cards": [
            {"title": "企业总数", "value": 12580, "trend": "+3.2%"},
            {"title": "招商机会", "value": 230, "trend": "+15%"},
            {"title": "高风险企业", "value": 20, "trend": "-5"},
            {"title": "AI任务", "value": 1520, "trend": "+8%"},
        ],
        "charts": [],
    }
    state["status"] = "insight"
    return state


def insight_engine(state: BIState) -> BIState:
    state["insight_result"] = {
        "summary": "园区运营稳定，机器人产业热度上升",
        "opportunities": [{"area": "核心零部件", "action": "重点关注传感器企业"}],
        "alerts": [],
    }
    state["status"] = "done"
    return state


def build_bi_graph():
    w = StateGraph(BIState)
    for n, f in [("router", query_router), ("kpi", kpi_calculator),
                  ("dashboard", dashboard_builder), ("insight", insight_engine)]:
        w.add_node(n, f)
    w.set_entry_point("router")
    for a, b in [("router","kpi"),("kpi","dashboard"),("dashboard","insight")]:
        w.add_edge(a, b)
    w.add_edge("insight", END)
    return w.compile()

_big = None
def get_bi_graph():
    global _big
    if _big is None: _big = build_bi_graph()
    return _big
