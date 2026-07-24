"""Policy RAG Agent LangGraph Nodes"""
import logging
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from app.tools.gateway import get_tool_gateway

logger = logging.getLogger(__name__)
tg = get_tool_gateway()


class PolicyState(TypedDict):
    task_id: str
    intent: str
    input: Dict[str, Any]
    query: str
    enterprise_id: Optional[str]
    enterprise_profile: Optional[Dict]
    raw_chunks: Optional[List[Dict]]
    filtered_chunks: Optional[List[Dict]]
    search_mode: Optional[str]
    matched_policies: Optional[List[Dict]]
    report: Optional[Dict]
    status: str
    error: Optional[Dict]
    tools_used: List[str]
    data_sources: List[str]


def query_analyzer_node(state: PolicyState) -> PolicyState:
    inp = state.get("input", {})
    state["query"] = inp.get("query", "")
    state["enterprise_id"] = inp.get("enterprise_id")
    state["tools_used"] = []
    state["data_sources"] = []
    state["status"] = "loading" if state["enterprise_id"] else "searching"
    return state


def enterprise_loader_node(state: PolicyState) -> PolicyState:
    if not state.get("enterprise_id"):
        state["status"] = "searching"
        return state
    r = tg.invoke("PolicyAgent", "enterprise_profile_get", {"enterprise_id": state["enterprise_id"]})
    state["enterprise_profile"] = r.data or {}
    state["tools_used"].append("enterprise_profile_get")
    state["data_sources"].append("enterprise_profile")
    state["status"] = "searching"
    return state


def vector_search_node(state: PolicyState) -> PolicyState:
    """向量/混合检索 — P1: 通过 KnowledgeTool (MockAdapter 或 pgvector)"""
    q = state["query"]
    filters = {}

    if state.get("enterprise_profile"):
        ind = state["enterprise_profile"].get("industry", "")
        loc = state["enterprise_profile"].get("location", "")
        if ind:
            q = f"{ind} {q}" if ind else q
            filters["industry"] = ind
        if loc:
            filters["region"] = loc

    # P1: 使用 policy_hybrid_search (KnowledgeTool → PolicyRetriever)
    r = tg.invoke("PolicyAgent", "policy_hybrid_search", {
        "query": q, "top_k": 10, "filters": filters,
    })
    state["raw_chunks"] = r.data.get("chunks", []) if r.status == "success" else []
    state["search_mode"] = r.data.get("mode", "mock") if r.status == "success" else "mock"
    state["tools_used"].append("policy_hybrid_search")
    state["data_sources"].append(f"policy_rag_{state['search_mode']}")
    state["status"] = "filtering"
    return state


def metadata_filter_node(state: PolicyState) -> PolicyState:
    """P1: 内存过滤 — hybrid_search 结果已包含过滤，只需排序去重"""
    chunks = state.get("raw_chunks", [])
    chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
    state["filtered_chunks"] = chunks[:10]
    state["status"] = "matching"
    return state


def policy_matcher_node(state: PolicyState) -> PolicyState:
    chunks = state.get("filtered_chunks", [])
    state["matched_policies"] = [
        {
            "policy_id": c.get("policy_id", ""),
            "title": c.get("metadata", {}).get("title", c.get("title", "")),
            "content_snippet": str(c.get("content", ""))[:200],
            "level": c.get("metadata", {}).get("level", c.get("level", "")),
            "department": c.get("metadata", {}).get("department", ""),
            "match_score": round(c.get("score", 0.7) * 100),
        }
        for c in chunks
    ]
    state["status"] = "formatting"
    return state


def response_formatter_node(state: PolicyState) -> PolicyState:
    state["report"] = {
        "query": state["query"],
        "total_matched": len(state.get("matched_policies", [])),
        "policies": state.get("matched_policies", []),
    }
    state["status"] = "done"
    return state


def build_policy_graph():
    workflow = StateGraph(PolicyState)
    nodes = [
        ("query_analyzer", query_analyzer_node),
        ("enterprise_loader", enterprise_loader_node),
        ("vector_search", vector_search_node),
        ("metadata_filter", metadata_filter_node),
        ("policy_matcher", policy_matcher_node),
        ("response_formatter", response_formatter_node),
    ]
    for name, node in nodes:
        workflow.add_node(name, node)
    workflow.set_entry_point("query_analyzer")
    for source, target in zip(nodes, nodes[1:]):
        workflow.add_edge(source[0], target[0])
    workflow.add_edge("response_formatter", END)
    return workflow.compile()


_policy_graph = None


def get_policy_graph():
    global _policy_graph
    if _policy_graph is None:
        _policy_graph = build_policy_graph()
    return _policy_graph
