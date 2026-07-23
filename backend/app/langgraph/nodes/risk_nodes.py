"""Risk Agent LangGraph Nodes — 6 节点 Pipeline + 预测"""
import logging
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from app.tools.gateway import get_tool_gateway

logger = logging.getLogger(__name__)
tg = get_tool_gateway()


class RiskState(TypedDict):
    task_id: str
    intent: str
    input: Dict[str, Any]
    enterprise_id: Optional[str]
    industry: Optional[str]
    basic_info: Optional[Dict]
    profile_data: Optional[Dict]
    risk_features: Optional[Dict]
    risk_score: Optional[float]
    risk_level: Optional[str]
    explanation: Optional[Dict]
    recommendation: Optional[str]
    report: Optional[Dict]
    prediction: Optional[Dict]
    status: str
    error: Optional[Dict]
    tools_used: List[str]
    data_sources: List[str]


def input_validator_node(state: RiskState) -> RiskState:
    eid = state.get("input", {}).get("enterprise_id") or state.get("enterprise_id")
    if not eid:
        state["status"] = "failed"
        state["error"] = {"code": "INVALID_INPUT", "message": "缺少 enterprise_id"}
        return state
    state["enterprise_id"] = eid
    state["tools_used"] = []
    state["data_sources"] = []
    state["status"] = "fetching"
    return state


def data_request_node(state: RiskState) -> RiskState:
    eid = state["enterprise_id"]
    profile = tg.invoke("RiskAgent", "enterprise_profile_get", {"enterprise_id": eid})
    basic = tg.invoke("RiskAgent", "enterprise_query", {"enterprise_id": eid})
    state["basic_info"] = basic.data or {}
    state["profile_data"] = profile.data or {}
    state["data_sources"] = ["enterprise", "enterprise_profile"]
    state["status"] = "extracting"
    return state


def _calc_feature(value: float, thresholds: tuple, scores: tuple) -> float:
    for t, s in zip(thresholds, scores):
        if value >= t: return s
    return scores[-1]


def feature_extractor_node(state: RiskState) -> RiskState:
    p = state.get("profile_data", {})
    features = {
        "business_risk": _calc_feature(p.get("growth_rate", 10), (20, 10, 0), (10, 30, 60)),
        "finance_risk": _calc_feature(p.get("funding_amount", 500), (500, 100, 0), (10, 30, 60)),
        "public_opinion_risk": 20,
        "legal_risk": 15,
        "talent_risk": _calc_feature(p.get("employee_count", 100), (200, 50, 0), (10, 30, 60)),
        "market_risk": 25,
    }
    state["risk_features"] = features
    state["status"] = "scoring"
    return state


def scoring_node(state: RiskState) -> RiskState:
    f = state["risk_features"]
    weights = {"business_risk": 0.30, "finance_risk": 0.25, "public_opinion_risk": 0.15,
               "legal_risk": 0.15, "talent_risk": 0.10, "market_risk": 0.05}
    score = round(sum(f[k] * weights[k] for k in weights), 1)
    state["risk_score"] = score
    state["risk_level"] = "LOW" if score <= 30 else ("MEDIUM" if score <= 70 else "HIGH")
    state["status"] = "explaining"
    return state


def explanation_node(state: RiskState) -> RiskState:
    f = state["risk_features"]
    factors = [{"type": k, "score": v} for k, v in sorted(f.items(), key=lambda x: -x[1]) if v > 30]
    state["explanation"] = {"risk_factors": factors}
    state["recommendation"] = (
        "建议园区立即走访" if state["risk_level"] == "HIGH"
        else "建议月度跟踪" if state["risk_level"] == "MEDIUM"
        else "正常关注"
    )
    state["status"] = "predicting"
    return state


def predict_node(state: RiskState) -> RiskState:
    """90 天风险预测"""
    score = state["risk_score"]
    history = tg.invoke("RiskAgent", "risk_history", {"enterprise_id": state["enterprise_id"]})
    trend = 0.05 if state["risk_level"] == "MEDIUM" else (0.1 if state["risk_level"] == "HIGH" else -0.02)
    state["prediction"] = {
        "current": score,
        "predicted_30d": min(100, score + trend * 1 * 30),
        "predicted_90d": min(100, score + trend * 3 * 30),
        "direction": "worsening" if trend > 0 else "improving",
    }
    state["status"] = "reporting"
    return state


def report_generator_node(state: RiskState) -> RiskState:
    state["report"] = {
        "enterprise_id": state["enterprise_id"],
        "enterprise_name": state.get("basic_info", {}).get("name", ""),
        "risk_score": state["risk_score"],
        "risk_level": state["risk_level"],
        "risk_factors": state.get("explanation", {}).get("risk_factors", []),
        "recommendation": state["recommendation"],
        "prediction": state["prediction"],
    }
    state["status"] = "done"
    return state


def build_risk_graph():
    workflow = StateGraph(RiskState)
    workflow.add_node("validate", input_validator_node)
    workflow.add_node("fetch", data_request_node)
    workflow.add_node("features", feature_extractor_node)
    workflow.add_node("score", scoring_node)
    workflow.add_node("explain", explanation_node)
    workflow.add_node("predict", predict_node)
    workflow.add_node("report_generator", report_generator_node)
    workflow.set_entry_point("validate")
    workflow.add_conditional_edges(
        "validate",
        lambda state: "failed" if state.get("status") == "failed" else "valid",
        {"failed": END, "valid": "fetch"},
    )
    for source, target in [
        ("fetch", "features"), ("features", "score"), ("score", "explain"),
        ("explain", "predict"), ("predict", "report_generator"),
    ]:
        workflow.add_edge(source, target)
    workflow.add_edge("report_generator", END)
    return workflow.compile()


_risk_graph = None


def get_risk_graph():
    global _risk_graph
    if _risk_graph is None:
        _risk_graph = build_risk_graph()
    return _risk_graph
