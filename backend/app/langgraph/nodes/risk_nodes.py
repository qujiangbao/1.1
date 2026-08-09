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
    risk_events: Optional[List[Dict]]
    business_status: Optional[Dict]
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

    # P0: 新增风险事件 + 经营状态
    risk_events = tg.invoke("RiskAgent", "enterprise_risk_events", {"enterprise_id": eid, "limit": 20})
    biz_status = tg.invoke("RiskAgent", "enterprise_business_status", {"enterprise_id": eid})

    state["basic_info"] = basic.data or {}
    state["profile_data"] = profile.data or {}
    state["risk_events"] = risk_events.data.get("events", []) if risk_events.status == "success" else []
    state["business_status"] = biz_status.data if biz_status.status == "success" else {}
    state["data_sources"] = ["enterprise", "enterprise_profile", "enterprise_risk_events", "enterprise_business_status"]
    state["status"] = "extracting"
    return state


def _calc_feature(value: float | None, thresholds: tuple, scores: tuple) -> float | None:
    if value is None:
        return None
    for t, s in zip(thresholds, scores):
        if value >= t: return s
    return scores[-1]


def feature_extractor_node(state: RiskState) -> RiskState:
    events = state.get("risk_events", []) or []
    level_score = {"HIGH": 90.0, "MEDIUM": 60.0, "LOW": 30.0}
    event_scores = [
        level_score.get(str(item.get("event_level") or "").upper())
        for item in events
    ]
    event_scores = [value for value in event_scores if value is not None]
    business_status = str(state.get("business_status", {}).get("status") or "").lower()
    features = {
        "verified_event_risk": max(event_scores) if event_scores else None,
        "registration_risk": (
            90.0 if business_status in {"abnormal", "revoked", "cancelled"} else None
        ),
    }
    state["risk_features"] = features
    state["status"] = "scoring"
    return state


def scoring_node(state: RiskState) -> RiskState:
    f = state["risk_features"]
    available = {key: value for key, value in f.items() if value is not None}
    if not available:
        state["risk_score"] = None
        state["risk_level"] = "UNKNOWN"
        state["status"] = "explaining"
        return state
    score = round(max(available.values()), 1)
    state["risk_score"] = score
    state["risk_level"] = "LOW" if score <= 30 else ("MEDIUM" if score <= 70 else "HIGH")
    state["status"] = "explaining"
    return state


def explanation_node(state: RiskState) -> RiskState:
    f = state["risk_features"]
    available = [(key, value) for key, value in f.items() if value is not None]
    factors = [
        {"type": key, "score": value}
        for key, value in sorted(available, key=lambda item: -item[1])
        if value > 30
    ]
    state["explanation"] = {"risk_factors": factors}
    state["recommendation"] = (
        "建议园区立即走访" if state["risk_level"] == "HIGH"
        else "建议月度跟踪" if state["risk_level"] == "MEDIUM"
        else "正常关注" if state["risk_level"] == "LOW"
        else "数据不足，暂不判定风险等级"
    )
    state["status"] = "predicting"
    return state


def predict_node(state: RiskState) -> RiskState:
    """Do not manufacture a forecast without a verified time series."""
    score = state["risk_score"]
    state["prediction"] = {
        "current": score,
        "predicted_30d": None,
        "predicted_90d": None,
        "direction": "unknown",
        "reason": "未接入连续风险事件时间序列，不生成预测值",
    }
    state["status"] = "reporting"
    return state


def report_generator_node(state: RiskState) -> RiskState:
    events = state.get("risk_events", []) or []
    reason = (
        f"核验到 {len(events)} 条风险事件，按最高事件等级给出当前风险提示"
        if events else "未取得可核验风险事件，不能据此认定低风险"
    )
    state["report"] = {
        "enterprise_id": state["enterprise_id"],
        "enterprise_name": state.get("basic_info", {}).get("name", ""),
        "risk_score": state["risk_score"],
        "risk_level": state["risk_level"],
        "risk_reason": reason,
        "risk_factors": state.get("explanation", {}).get("risk_factors", []),
        "recommendation": state["recommendation"],
        "action": state["recommendation"],
        "risk_events": events,
        "business_status": state.get("business_status", {}),
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
