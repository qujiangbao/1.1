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
    data_mode: str
    status: str


def query_router(state: BIState) -> BIState:
    inp = state.get("input", {})
    state["intent"] = inp.get("intent", "dashboard_kpi")
    state["dashboard_type"] = inp.get("dashboard_type", "overview")
    state["data_mode"] = str(inp.get("data_mode", "real")).lower()
    state["status"] = "computing"
    return state


def kpi_calculator(state: BIState) -> BIState:
    if state.get("data_mode") == "demo":
        from app.services.demo_scenario import DEMO_FUNNEL, DEMO_RISK_ENTERPRISES

        high = sum(1 for item in DEMO_RISK_ENTERPRISES if item["level"] == "high")
        medium = sum(1 for item in DEMO_RISK_ENTERPRISES if item["level"] == "medium")
        low = sum(1 for item in DEMO_RISK_ENTERPRISES if item["level"] == "low")
        state["kpi_result"] = {
            "park_overview": {
                "total_enterprises": DEMO_FUNNEL[0]["count"],
                "growth_rate": None,
                "data_mode": "demo",
            },
            "investment": {
                "opportunities": DEMO_FUNNEL[0]["count"],
                "signed": DEMO_FUNNEL[-1]["count"],
                "conversion_rate": round(
                    DEMO_FUNNEL[-1]["count"] / DEMO_FUNNEL[0]["count"] * 100,
                    1,
                ),
                "data_mode": "demo",
            },
            "risk": {
                "high_risk": high,
                "medium_risk": medium,
                "low_risk": low,
                "data_mode": "demo",
            },
            "ai_operations": {
                "agent_calls": None,
                "success_rate": None,
                "data_status": "DATA_INSUFFICIENT",
                "data_mode": "demo",
            },
        }
    else:
        # This graph does not own dashboard/database aggregation.  Public-mode
        # metrics must never fall back to historical competition constants.
        state["kpi_result"] = {
            "park_overview": {
                "total_enterprises": None,
                "growth_rate": None,
                "data_status": "DATA_INSUFFICIENT",
                "data_mode": "real",
            },
            "investment": {
                "opportunities": None,
                "signed": None,
                "conversion_rate": None,
                "data_status": "DATA_INSUFFICIENT",
                "data_mode": "real",
            },
            "risk": {
                "high_risk": None,
                "medium_risk": None,
                "low_risk": None,
                "risk_level": "UNKNOWN",
                "data_mode": "real",
            },
            "ai_operations": {
                "agent_calls": None,
                "success_rate": None,
                "data_status": "DATA_INSUFFICIENT",
                "data_mode": "real",
            },
        }
    state["status"] = "building_dashboard"
    return state


def dashboard_builder(state: BIState) -> BIState:
    kpi = state.get("kpi_result") or {}
    state["dashboard_result"] = {
        "cards": [
            {
                "title": "企业总数",
                "value": kpi.get("park_overview", {}).get("total_enterprises"),
                "data_status": kpi.get("park_overview", {}).get("data_status"),
            },
            {
                "title": "招商机会",
                "value": kpi.get("investment", {}).get("opportunities"),
                "data_status": kpi.get("investment", {}).get("data_status"),
            },
            {
                "title": "高风险企业",
                "value": kpi.get("risk", {}).get("high_risk"),
                "data_status": (
                    "UNKNOWN"
                    if kpi.get("risk", {}).get("risk_level") == "UNKNOWN"
                    else None
                ),
            },
            {
                "title": "AI任务",
                "value": kpi.get("ai_operations", {}).get("agent_calls"),
                "data_status": kpi.get("ai_operations", {}).get("data_status"),
            },
        ],
        "charts": [],
        "data_mode": state.get("data_mode", "real"),
    }
    state["status"] = "insight"
    return state


def insight_engine(state: BIState) -> BIState:
    if state.get("data_mode") == "demo":
        state["insight_result"] = {
            "summary": "演示沙盘指标来自固定合成场景，非真实经营数据。",
            "opportunities": [
                {"area": "核心零部件", "action": "演示建议：进入人工复核。"}
            ],
            "alerts": [],
            "data_mode": "demo",
        }
    else:
        state["insight_result"] = {
            "summary": (
                "当前 BI Agent 未接入可核验的经营指标聚合结果；"
                "公开模式不生成招商、签约、增长或风险数量结论。"
            ),
            "opportunities": [],
            "alerts": [
                {
                    "level": "warning",
                    "message": "DATA_INSUFFICIENT：请通过驾驶舱聚合 API 获取有来源的指标。",
                }
            ],
            "data_mode": "real",
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
