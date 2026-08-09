"""Agent Registry — Supervisor 通过此注册表发现和调用 Agent"""
from typing import Dict
from app.schemas.agent import AgentCapability


AGENT_REGISTRY: Dict[str, dict] = {
    "InvestmentAgent": {
        "name": "InvestmentAgent",
        "display": "AI招商经理",
        "capabilities": [
            "enterprise_search", "enterprise_profile",
            "enterprise_scoring", "investment_recommend",
            "investment_strategy"
        ],
        "timeout_ms": 30000,
        "retry_count": 2,
    },
    "PolicyAgent": {
        "name": "PolicyAgent",
        "display": "AI政策顾问",
        "capabilities": [
            "policy_search", "policy_match",
            "policy_recommend", "policy_analysis"
        ],
        "timeout_ms": 20000,
        "retry_count": 2,
    },
    "IndustryAgent": {
        "name": "IndustryAgent",
        "display": "AI产业研究院",
        "capabilities": [
            "industry_chain_analysis", "industry_trend",
            "market_analysis", "investment_direction"
        ],
        "timeout_ms": 25000,
        "retry_count": 2,
    },
    "RiskAgent": {
        "name": "RiskAgent",
        "display": "企业风险雷达",
        "capabilities": [
            "risk_score", "risk_analysis",
            "risk_report", "batch_risk_scan", "risk_trend"
        ],
        "timeout_ms": 20000,
        "retry_count": 2,
    },
    "EnterpriseServiceAgent": {
        "name": "EnterpriseServiceAgent",
        "display": "AI企业服务助手",
        "capabilities": [
            "service_request_classification", "service_guidance",
            "manual_handoff_advice"
        ],
        "timeout_ms": 30000,
        "retry_count": 2,
    },
    "BIAgent": {
        "name": "BIAgent",
        "display": "AI经营分析师",
        "capabilities": [
            "kpi_query", "dashboard_data",
            "chart_generation", "ai_insight"
        ],
        "timeout_ms": 15000,
        "retry_count": 1,
    },
}


async def init_agent_registry():
    """启动时初始化 Agent 注册表"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Agent Registry loaded: {len(AGENT_REGISTRY)} agents")
    for name, info in AGENT_REGISTRY.items():
        logger.info(f"  {name}: {info['capabilities']}")


def get_agent_info(agent_name: str) -> dict | None:
    return AGENT_REGISTRY.get(agent_name)


def find_agent_by_capability(capability: str) -> str | None:
    for name, info in AGENT_REGISTRY.items():
        if capability in info["capabilities"]:
            return name
    return None
