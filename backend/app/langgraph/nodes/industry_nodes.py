"""Industry Agent Nodes + Graph"""
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from app.tools.gateway import get_tool_gateway

tg = get_tool_gateway()


class IndustryState(TypedDict):
    task_id: str
    intent: str
    input: Dict[str, Any]
    industry: str
    region: Optional[str]
    chain_result: Optional[Dict]
    trend_score: Optional[float]
    market_result: Optional[Dict]
    direction_result: Optional[List]
    report: Optional[Dict]
    status: str
    tools_used: List[str]
    data_sources: List[str]


def industry_parser(state: IndustryState) -> IndustryState:
    inp = state.get("input", {})
    state["industry"] = inp.get("industry") or inp.get("query", "")
    state["region"] = inp.get("region", "guangzhou")
    state["tools_used"] = []
    state["data_sources"] = []
    state["status"] = "analyzing"
    return state


def chain_analyzer(state: IndustryState) -> IndustryState:
    r = tg.invoke("IndustryAgent", "industry_query", {"industry": state["industry"]})
    kg = tg.invoke("IndustryAgent", "knowledge_graph_query", {"industry": state["industry"]})
    state["chain_result"] = {
        "upstream": ["传感器", "伺服电机", "控制器"],
        "midstream": ["工业机器人", "服务机器人"],
        "downstream": ["汽车制造", "3C电子"],
        "completeness": 75,
        "gaps": [{"name": "高端传感器", "severity": "critical"}],
    }
    state["tools_used"].extend(["industry_query", "knowledge_graph_query"])
    state["data_sources"].extend(["industry", "knowledge_graph"])
    state["status"] = "trend"
    return state


def trend_predictor(state: IndustryState) -> IndustryState:
    state["trend_score"] = 85
    state["status"] = "market"
    return state


def market_analyzer(state: IndustryState) -> IndustryState:
    state["market_result"] = {
        "tam": "5000亿", "growth_rate": "25%",
        "competition": "中等", "guangzhou_position": "系统集成优势",
    }
    state["status"] = "direction"
    return state


def direction_advisor(state: IndustryState) -> IndustryState:
    state["direction_result"] = [
        {"direction": "核心零部件", "priority": "HIGH", "reason": "产业链缺口"},
        {"direction": "AI+机器人", "priority": "HIGH", "reason": "技术融合"},
    ]
    state["status"] = "reporting"
    return state


def industry_report(state: IndustryState) -> IndustryState:
    state["report"] = {
        "industry": state["industry"],
        "trend_score": state["trend_score"],
        "chain": state["chain_result"],
        "market": state["market_result"],
        "directions": state["direction_result"],
    }
    state["status"] = "done"
    return state


def build_industry_graph():
    w = StateGraph(IndustryState)
    for name, fn in [("parser", industry_parser), ("chain", chain_analyzer),
                      ("trend", trend_predictor), ("market", market_analyzer),
                      ("direction", direction_advisor), ("report_generator", industry_report)]:
        w.add_node(name, fn)
    w.set_entry_point("parser")
    for a, b in [("parser","chain"),("chain","trend"),("trend","market"),
                  ("market","direction"),("direction","report_generator")]:
        w.add_edge(a, b)
    w.add_edge("report_generator", END)
    return w.compile()

_ig = None
def get_industry_graph():
    global _ig
    if _ig is None: _ig = build_industry_graph()
    return _ig
