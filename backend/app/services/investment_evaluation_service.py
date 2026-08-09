"""Create stable, reviewable recommendation snapshots for one scenario."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.investment import InvestmentScenario
from app.schemas.enterprise import EnterpriseProfile
from app.schemas.investment_candidate import (
    InvestmentScenarioCreate,
    RecommendationCard,
    RecommendationResponse,
)
from app.services.investment_scoring_service import (
    SCORING_VERSION,
)
from app.services.investment_decision_graph import run_investment_decision


DEMO_PROFILE_DETAIL: dict[str, dict[str, Any]] = {
    "智能传感器": {
        "business_scope": "核心零部件 系统集成 工业软件 智能传感器研发制造，MEMS传感器、工业物联网传感器模组设计与销售，自动化检测系统集成，机器人 智能制造 高端装备产业链核心配套",
        "location": "广州南沙",
        "capital_amount": 8000.0,
        "enterprise_status": "存续",
        "patents_count": 48,
        "growth_rate": 28.5,
        "funding_stage": "B轮",
        "expansion_willingness": "已在南沙设立研发中心，计划两年内扩建生产线",
        "website": "https://demo-sensor-tech.com",
        "tags": ["机器人", "智能制造", "高端装备", "核心零部件", "高新技术企业", "专精特新", "智能传感器"],
    },
    "工业机器人": {
        "business_scope": "核心零部件 系统集成 工业机器人整机及核心零部件研发制造，六轴机器人、SCARA机器人、协作机器人生产销售，自动化产线集成，机器人 智能制造 高端装备",
        "location": "广州黄埔",
        "capital_amount": 25000.0,
        "enterprise_status": "存续",
        "patents_count": 126,
        "growth_rate": 35.2,
        "funding_stage": "C轮",
        "expansion_willingness": "黄埔工厂二期已启动，规划产能翻倍",
        "website": "https://demo-robot-industrial.com",
        "tags": ["机器人", "智能制造", "高端装备", "系统集成", "高新技术企业", "小巨人", "工业机器人"],
    },
    "伺服与驱动": {
        "business_scope": "核心零部件 工业软件 伺服驱动器、伺服电机、运动控制器研发制造，机器人关节模组、高精度减速器生产，机器人 智能制造 高端装备",
        "location": "广州天河",
        "capital_amount": 12000.0,
        "enterprise_status": "存续",
        "patents_count": 73,
        "growth_rate": 22.8,
        "funding_stage": "B轮",
        "expansion_willingness": "有意向在广州开发区落地新产线",
        "website": "https://demo-servo-drive.com",
        "tags": ["机器人", "智能制造", "高端装备", "核心零部件", "高新技术企业", "伺服与驱动"],
    },
    "机器视觉": {
        "business_scope": "系统集成 工业软件 工业机器视觉系统研发，3D视觉传感器、缺陷检测算法平台、AI质检解决方案，机器人 智能制造 高端装备",
        "location": "广州番禺",
        "capital_amount": 5000.0,
        "enterprise_status": "存续",
        "patents_count": 35,
        "growth_rate": 40.1,
        "funding_stage": "A轮",
        "expansion_willingness": "已完成A轮融资，计划广州设立总部",
        "website": "https://demo-vision-ai.com",
        "tags": ["科技型中小企业", "机器视觉", "人工智能"],
    },
    "控制系统": {
        "business_scope": "核心零部件 系统集成 工业软件 机器人控制系统、运动控制卡、PLC控制器研发，工业软件平台、数字孪生系统开发，机器人 智能制造 高端装备",
        "location": "广州海珠",
        "capital_amount": 6500.0,
        "enterprise_status": "存续",
        "patents_count": 52,
        "growth_rate": 18.6,
        "funding_stage": "A轮",
        "expansion_willingness": "存在潜在扩产意愿（信号较弱）",
        "website": "https://demo-control-sys.com",
        "tags": ["机器人", "智能制造", "高端装备", "工业软件", "创新型企业", "控制系统"],
    },
}


def _demo_profiles(limit: int) -> list[EnterpriseProfile]:
    from app.services.demo_scenario import DEMO_INVESTMENT_TARGETS

    collected_at = datetime.now(timezone.utc)
    profiles: list[EnterpriseProfile] = []
    for item in DEMO_INVESTMENT_TARGETS[:limit]:
        detail = DEMO_PROFILE_DETAIL.get(item["industry"], {})
        # Prepend policy-matching keywords so INDUSTRY_MATCH condition hits
        policy_industry = f"机器人 智能制造 高端装备 · {item['industry']}"
        profiles.append(
            EnterpriseProfile(
                enterprise_id=item["enterprise_id"],
                name=item["name"],
                industry=policy_industry,
                business_scope=detail.get("business_scope", "演示字段：机器人产业链能力"),
                location=detail.get("location", "演示园区"),
                capital_amount=detail.get("capital_amount"),
                enterprise_status=detail.get("enterprise_status", "存续"),
                patents_count=detail.get("patents_count"),
                growth_rate=detail.get("growth_rate"),
                funding_stage=detail.get("funding_stage"),
                expansion_willingness=detail.get("expansion_willingness"),
                website=detail.get("website"),
                match_reason=item["evidence"],
                tags=detail.get("tags", ["演示沙盘", item["industry"], "机器人"]),
                data_source="demo_scenario",
                source_time=collected_at,
                confidence_score=0.75,
                evidence=[
                    {"type": "synthetic", "value": "演示沙盘合成数据：产业匹配、技术能力、成长性和扩产意愿均有仿真值", "url": ""}
                ],
            )
        )
    return profiles


async def _profiles(
    request: InvestmentScenarioCreate,
) -> tuple[list[EnterpriseProfile], dict[str, Any], list[str]]:
    if request.data_mode == "demo":
        profiles = _demo_profiles(request.limit)
        return (
            profiles,
            {
                "source": "demo_scenario",
                "catalog_total": 36,
                "returned": len(profiles),
                "is_demo": True,
            },
            ["固定合成场景，仅用于演示流程，不代表真实企业或招商结论。"],
        )

    from app.tools.enterprise_data import get_enterprise_data_tool

    tool = get_enterprise_data_tool()
    query = " ".join(
        [request.industry, *request.target_chain_roles]
    ).strip()
    result = await tool.search_enterprises(
        query,
        location=request.location_preference,
        limit=min(40, request.limit * 4),
    )
    stats = tool.stats()
    profiles = list(result.enterprises)
    source_summary = {
        "source": result.data_source,
        "catalog_total": stats.get("total_enterprises"),
        "matched": result.total,
        "scored": len(profiles),
        "coverage": stats.get("coverage", {}),
        "snapshot_updated_at": stats.get("last_updated"),
        "is_demo": False,
    }
    limitations = list(stats.get("limitations", []))
    limitations.extend(
        [
            "推荐分数只对有证据维度归一化，缺失字段不按 0 分处理。",
            "风险无记录时返回 UNKNOWN；政策相关不等于符合申报条件。",
        ]
    )
    return profiles, source_summary, limitations


async def create_scenario(
    session: AsyncSession,
    request: InvestmentScenarioCreate,
    *,
    user_id: str,
) -> InvestmentScenario:
    profiles, source_summary, limitations = await _profiles(request)
    decision_run = await run_investment_decision(request, profiles)
    recommendations = decision_run.recommendations
    generated_at = decision_run.generated_at
    source_summary = {
        **source_summary,
        "orchestration": {
            "run_id": decision_run.run_id,
            "version": decision_run.version,
            "agents": [
                "Supervisor",
                "IndustryAgent",
                "InvestmentAgent",
                "EnterpriseData",
                "RiskAgent",
                "PolicyAgent",
                "RuleAggregator",
            ],
            "enterprise_count": len(recommendations),
        },
    }
    for warning in decision_run.warnings:
        if warning not in limitations:
            limitations.append(warning)
    scenario = InvestmentScenario(
        name=request.name,
        industry=request.industry,
        target_chain_roles=request.target_chain_roles,
        location_preference=request.location_preference,
        result_limit=request.limit,
        data_mode=request.data_mode,
        status="READY",
        recommendation_snapshot=[
            item.model_dump(mode="json") for item in recommendations
        ],
        snapshot_metadata={
            "generated_at": generated_at.isoformat(),
            "version": SCORING_VERSION,
            "orchestration_version": decision_run.version,
            "decision_run_id": decision_run.run_id,
            "supervisor_output": decision_run.supervisor_output.model_dump(
                mode="json"
            ),
            "industry_output": decision_run.industry_output.model_dump(
                mode="json"
            ),
            "source_summary": source_summary,
            "limitations": limitations,
            "scoring_weights": request.weights,
        },
        created_by=user_id,
    )
    session.add(scenario)
    await session.commit()
    await session.refresh(scenario)
    return scenario


def scenario_response(scenario: InvestmentScenario) -> RecommendationResponse:
    metadata = scenario.snapshot_metadata or {}
    generated_at = metadata.get("generated_at") or scenario.created_at
    return RecommendationResponse(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        data_mode=scenario.data_mode,
        generated_at=generated_at,
        version=metadata.get("version", SCORING_VERSION),
        source_summary=metadata.get("source_summary", {}),
        limitations=metadata.get("limitations", []),
        recommendations=[
            RecommendationCard.model_validate(item)
            for item in (scenario.recommendation_snapshot or [])
        ],
    )
