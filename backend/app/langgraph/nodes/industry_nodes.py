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
    enterprise_sample: Optional[List[Dict]]
    enterprise_total: Optional[int]


CHAIN_TERMS = {
    "upstream": {
        "label": "核心零部件与基础能力",
        "terms": ("传感器", "伺服", "驱动", "减速器", "控制器", "芯片", "电机", "关节"),
    },
    "midstream": {
        "label": "本体、平台与系统集成",
        "terms": ("机器人", "机械臂", "本体", "系统集成", "自动化", "智能装备", "操作系统"),
    },
    "downstream": {
        "label": "场景应用与服务",
        "terms": ("医疗", "物流", "教育", "巡检", "仓储", "汽车", "制造", "服务", "无人机"),
    },
}

INDUSTRY_QUERY_TERMS = (
    "具身智能",
    "人工智能",
    "智能制造",
    "工业机器人",
    "机器人",
    "新能源",
    "新材料",
    "集成电路",
    "半导体",
    "生物医药",
    "数字经济",
    "低空经济",
)


def _focus_industry_query(value: str) -> str:
    """Reduce a compound user request to searchable industry concepts."""
    text = str(value or "").strip()
    matched = [term for term in INDUSTRY_QUERY_TERMS if term in text]
    return " ".join(dict.fromkeys(matched)) or text


def industry_parser(state: IndustryState) -> IndustryState:
    inp = state.get("input", {})
    state["industry"] = _focus_industry_query(
        inp.get("industry") or inp.get("query", "")
    )
    raw_region = str(inp.get("region") or "广州").strip()
    state["region"] = {
        "guangzhou": "广州",
        "gz": "广州",
    }.get(raw_region.lower(), raw_region)
    state["tools_used"] = []
    state["data_sources"] = []
    state["status"] = "analyzing"
    return state


def chain_analyzer(state: IndustryState) -> IndustryState:
    result = tg.invoke("IndustryAgent", "enterprise_search", {
        "query": state["industry"],
        "industry": state["industry"],
        "location": state.get("region"),
        "limit": 200,
    })
    enterprises = result.data.get("enterprises", []) if result.status == "success" else []
    state["enterprise_sample"] = enterprises
    state["enterprise_total"] = result.data.get("total", len(enterprises)) if result.status == "success" else 0
    state["tools_used"].append("enterprise_search")
    state["data_sources"].append("enterprise_public_snapshot")

    classified: dict[str, list[dict[str, str]]] = {key: [] for key in CHAIN_TERMS}
    for item in enterprises:
        searchable = " ".join(str(item.get(key) or "") for key in (
            "name", "industry", "business_scope", "match_reason", "tags"
        )).lower()
        for layer, config in CHAIN_TERMS.items():
            matched = [term for term in config["terms"] if term.lower() in searchable]
            if matched:
                classified[layer].append({
                    "enterprise_id": str(item.get("enterprise_id") or ""),
                    "name": str(item.get("name") or ""),
                    "matched_terms": "、".join(matched[:4]),
                })

    sample_size = len(enterprises)
    covered_layers = sum(
        bool(items) and (sample_size < 10 or len(items) / sample_size >= 0.15)
        for items in classified.values()
    )
    gaps = [
        {
            "name": config["label"],
            "reason": (
                "当前企业公开快照未检索到该环节的可验证企业线索"
                if not classified[layer]
                else (
                    f"当前快照仅有 {len(classified[layer])} 条相关线索，"
                    f"占本次样本 {len(classified[layer]) / sample_size:.1%}，建议优先补充核验"
                )
            ),
            "gap_type": "snapshot_coverage",
            "enterprise_count": len(classified[layer]),
            "sample_ratio": round(len(classified[layer]) / sample_size, 4) if sample_size else 0,
        }
        for layer, config in CHAIN_TERMS.items()
        if not classified[layer] or (sample_size >= 10 and len(classified[layer]) / sample_size < 0.15)
    ]
    state["chain_result"] = {
        "upstream": classified["upstream"][:8],
        "midstream": classified["midstream"][:8],
        "downstream": classified["downstream"][:8],
        "layer_counts": {key: len(value) for key, value in classified.items()},
        "enterprise_total": state["enterprise_total"],
        "sample_size": sample_size,
        "completeness": round(covered_layers / len(CHAIN_TERMS) * 100, 1),
        "gaps": gaps,
        "status": "snapshot_evidence" if enterprises else "not_connected",
        "note": (
            "仅表示当前公开企业快照的产业链覆盖，不等同于真实市场份额或产业缺口。"
            if enterprises else "未检索到可验证企业快照，未生成产业链判断。"
        ),
    }
    state["status"] = "trend"
    return state


def trend_predictor(state: IndustryState) -> IndustryState:
    state["trend_score"] = None
    state["status"] = "market"
    return state


def market_analyzer(state: IndustryState) -> IndustryState:
    state["market_result"] = {
        "tam": None,
        "growth_rate": None,
        "competition": None,
        "guangzhou_position": None,
        "enterprise_snapshot_count": state.get("enterprise_total", 0),
        "status": "partial" if state.get("enterprise_total") else "not_connected",
        "note": "尚无权威市场规模与时间序列，企业数量仅为当前快照召回量。",
    }
    state["status"] = "direction"
    return state


def direction_advisor(state: IndustryState) -> IndustryState:
    gaps = state.get("chain_result", {}).get("gaps", [])
    state["direction_result"] = [
        {
            "direction": f"补充{item['name']}企业线索",
            "priority": "HIGH",
            "reason": item["reason"],
            "decision_boundary": "线索库覆盖建议，不代表市场供给结论",
        }
        for item in gaps
    ] or [{
        "direction": "核验各产业链环节代表企业",
        "priority": "MEDIUM",
        "reason": "当前快照已覆盖三个环节，但仍需权威产业统计和企业走访验证",
        "decision_boundary": "不得据此推断市场规模或增长趋势",
    }]
    state["status"] = "reporting"
    return state


def industry_report(state: IndustryState) -> IndustryState:
    state["report"] = {
        "industry": state["industry"],
        "trend_score": state["trend_score"],
        "chain": state["chain_result"],
        "market": state["market_result"],
        "directions": state["direction_result"],
        "evidence_level": "partial" if state.get("enterprise_total") else "insufficient",
        "data_sources": state.get("data_sources", []),
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
