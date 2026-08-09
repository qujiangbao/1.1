"""Deterministic synthetic scenario used by the presentation sandbox.

The scenario deliberately uses obviously synthetic enterprise names.  It must
never be mixed into the public-snapshot mode or persisted as operational data.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


SCENARIO_ID = "robotics-park-demo-v1"
SCENARIO_NAME = "机器人产业园运营演示沙盘"
DEMO_DISCLAIMER = "演示沙盘 · 以下企业、招商、风险与经营数据均为合成数据，非真实经营数据。"

DEMO_INDUSTRIES = [
    {"name": "工业机器人", "value": 12},
    {"name": "智能传感器", "value": 7},
    {"name": "伺服与驱动", "value": 6},
    {"name": "控制系统", "value": 5},
    {"name": "系统集成", "value": 4},
    {"name": "产业服务", "value": 2},
]

DEMO_FUNNEL = [
    {"stage": "目标池", "count": 36},
    {"stage": "初步接触", "count": 22},
    {"stage": "深度洽谈", "count": 11},
    {"stage": "意向签约", "count": 5},
    {"stage": "正式入驻", "count": 2},
]

DEMO_RISK_TREND = [
    {"month": "2026-02", "high": 5, "medium": 10, "low": 21},
    {"month": "2026-03", "high": 5, "medium": 9, "low": 22},
    {"month": "2026-04", "high": 4, "medium": 10, "low": 22},
    {"month": "2026-05", "high": 4, "medium": 9, "low": 23},
    {"month": "2026-06", "high": 3, "medium": 9, "low": 24},
    {"month": "2026-07", "high": 3, "medium": 8, "low": 25},
]

DEMO_RISK_ENTERPRISES = [
    {
        "risk_id": "DEMO-RISK-001",
        "enterprise_id": "DEMO-TARGET-002",
        "name": "示例招商企业-002",
        "score": 32,
        "level": "low",
        "reason": "主要客户为行业头部企业，订单结构健康",
        "risk_type": "customer_concentration",
        "trend": "stable",
        "action": "关注大客户集中度变化，保持常规监测",
    },
    {
        "risk_id": "DEMO-RISK-002",
        "enterprise_id": "DEMO-TARGET-003",
        "name": "示例招商企业-003",
        "score": 55,
        "level": "medium",
        "reason": "关键零部件进口占比偏高，供应链存在单一来源风险",
        "risk_type": "supply_chain",
        "trend": "up",
        "action": "建议评估国产替代方案，启动备选供应商评估",
    },
    {
        "risk_id": "DEMO-RISK-003",
        "enterprise_id": "DEMO-TARGET-004",
        "name": "示例招商企业-004",
        "score": 48,
        "level": "medium",
        "reason": "A轮早期企业，研发费用高，经营性现金流为负",
        "risk_type": "cashflow",
        "trend": "stable",
        "action": "核验融资到账情况和研发转化进度",
    },
    {
        "risk_id": "DEMO-RISK-004",
        "enterprise_id": "DEMO-TARGET-005",
        "name": "示例招商企业-005",
        "score": 25,
        "level": "low",
        "reason": "已有稳定客户基础，产品交付周期正常",
        "risk_type": "delivery",
        "trend": "stable",
        "action": "保持常规监测",
    },
    {
        "risk_id": "DEMO-RISK-005",
        "enterprise_id": "DEMO-TARGET-001",
        "name": "示例招商企业-001",
        "score": 28,
        "level": "low",
        "reason": "近三年无重大诉讼或行政处罚，回款周期稳定",
        "risk_type": "routine",
        "trend": "down",
        "action": "保持常规监测",
    },
]

DEMO_INVESTMENT_TARGETS = [
    {
        "enterprise_id": f"DEMO-TARGET-{index:03d}",
        "name": f"示例招商企业-{index:03d}",
        "industry": industry,
        "score": score,
        "level": "STRONG_RECOMMEND" if score >= 85 else "RECOMMEND",
        "action": "演示建议：进入下一轮人工尽调",
        "evidence": "演示规则：产业匹配、成长性、技术能力三项合成评分",
    }
    for index, (industry, score) in enumerate(
        [
            ("智能传感器", 91),
            ("工业机器人", 88),
            ("伺服与驱动", 85),
            ("机器视觉", 82),
            ("控制系统", 79),
        ],
        start=1,
    )
]


def metadata() -> dict[str, Any]:
    return {
        "presentation_mode": "demo",
        "is_demo": True,
        "scenario_id": SCENARIO_ID,
        "scenario_name": SCENARIO_NAME,
        "disclaimer": DEMO_DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "resettable": True,
    }


def risk_dashboard(limit: int = 50) -> dict[str, Any]:
    items = deepcopy(DEMO_RISK_ENTERPRISES[:limit])
    generated_at = datetime.now(timezone.utc).isoformat()
    for item in items:
        item["source"] = "演示规则引擎"
        item["created_at"] = generated_at
    return {
        "data_available": True,
        "is_demo": True,
        "disclaimer": DEMO_DISCLAIMER,
        "scenario_id": SCENARIO_ID,
        "total_enterprises": 36,
        "evaluated_enterprises": 5,
        "coverage_pct": 14,
        "distribution": {"high": 0, "medium": 2, "low": 3},
        "trend": deepcopy(DEMO_RISK_TREND),
        "enterprises": items,
        "summary": "演示场景已对本次招商推荐的 5 家企业完成风险评估，其中中风险 2 家。",
        "insights": [
            "演示风险数据与招商目标企业联动，每家企业的风险等级反映在决策卡中。",
            "本页数据只用于展示风险发现、筛选与处置流程。",
        ],
        "source": "demo_scenario",
        "generated_at": generated_at,
    }


def agent_result(agent_name: str) -> dict[str, Any] | None:
    """Return a coherent synthetic result for non-policy demo agents."""
    if agent_name == "IndustryAgent":
        return {
            "industry": "机器人产业",
            "trend_score": 82,
            "chain": {
                "upstream": ["智能传感器", "伺服与驱动", "控制系统"],
                "midstream": ["工业机器人", "机器视觉"],
                "downstream": ["汽车制造", "3C 电子"],
                "completeness": 72,
                "gaps": [{"name": "高端传感器", "severity": "critical"}],
            },
            "market": {
                "growth_rate": "演示指数：18%",
                "competition": "演示等级：中等",
            },
            "directions": [
                {"direction": "高端传感器", "priority": "HIGH", "reason": "演示产业链缺口"},
                {"direction": "机器人控制系统", "priority": "HIGH", "reason": "演示场景需求"},
            ],
            "evidence_level": "synthetic",
            "disclaimer": DEMO_DISCLAIMER,
        }
    if agent_name == "InvestmentAgent":
        return {
            "summary": {"total_found": 36, "recommended": 5},
            "enterprises": deepcopy(DEMO_INVESTMENT_TARGETS),
            "strategy": {
                "summary": "演示场景从 36 家示例企业中筛选 5 家进入人工尽调。",
                "targets": deepcopy(DEMO_INVESTMENT_TARGETS),
            },
            "evidence_level": "synthetic",
            "disclaimer": DEMO_DISCLAIMER,
        }
    if agent_name == "RiskAgent":
        item = deepcopy(DEMO_RISK_ENTERPRISES[0])
        return {
            "enterprise_id": item["enterprise_id"],
            "enterprise_name": item["name"],
            "risk_score": item["score"],
            "risk_level": item["level"].upper(),
            "risk_reason": item["reason"],
            "action": item["action"],
            "evidence_level": "synthetic",
            "disclaimer": DEMO_DISCLAIMER,
        }
    if agent_name == "BIAgent":
        return {
            "kpi": {
                "enterprise_total": 36,
                "investment_targets": 36,
                "risk_high": 3,
            },
            "dashboard": {
                "investment_funnel": deepcopy(DEMO_FUNNEL),
                "risk_trend": deepcopy(DEMO_RISK_TREND),
            },
            "insight": {
                "summary": "演示沙盘显示：招商目标池 36 家，5 家进入意向阶段；高风险示例企业 3 家。"
            },
            "evidence_level": "synthetic",
            "disclaimer": DEMO_DISCLAIMER,
        }
    return None
