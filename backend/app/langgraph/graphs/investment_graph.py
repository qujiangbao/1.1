"""Investment Agent LangGraph"""
from langgraph.graph import StateGraph, END
from app.langgraph.nodes.investment_state import InvestmentState
from app.langgraph.nodes.investment_nodes import (
    intent_parser_node, enterprise_search_node, enterprise_profile_node,
    scoring_node, recommendation_node, strategy_generator_node, report_generator_node,
)


def build_investment_graph() -> StateGraph:
    workflow = StateGraph(InvestmentState)

    workflow.add_node("intent_parser", intent_parser_node)
    workflow.add_node("enterprise_search", enterprise_search_node)
    workflow.add_node("enterprise_profile", enterprise_profile_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("recommendation", recommendation_node)
    workflow.add_node("strategy_generator", strategy_generator_node)
    workflow.add_node("report_generator", report_generator_node)

    workflow.set_entry_point("intent_parser")
    workflow.add_edge("intent_parser", "enterprise_search")
    workflow.add_conditional_edges("enterprise_search", lambda s: "profiling" if s.get("profiles") is None and s.get("status") == "profiling" else END,
                                   {"profiling": "enterprise_profile", END: END})
    workflow.add_edge("enterprise_profile", "scoring")
    workflow.add_edge("scoring", "recommendation")
    workflow.add_edge("recommendation", "strategy_generator")
    workflow.add_edge("strategy_generator", "report_generator")
    workflow.add_edge("report_generator", END)

    return workflow.compile()


_investment_graph = None


def get_investment_graph():
    global _investment_graph
    if _investment_graph is None:
        _investment_graph = build_investment_graph()
    return _investment_graph
