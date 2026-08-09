"""Build dashboard payloads from operational and business data."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from time import monotonic
from typing import Any

from app.agents.registry import AGENT_REGISTRY
from app.services.runtime_metrics import get_runtime_metrics


COLORS = ["#1677ff", "#52c41a", "#faad14", "#722ed1", "#13c2c2", "#eb2f96"]
_BUSINESS_METRICS_TTL_SECONDS = 15.0
_BUSINESS_METRICS_CACHE: tuple[int, float, dict[str, Any]] | None = None
_BUSINESS_METRICS_LOCK = asyncio.Lock()


def _empty_agent_stat() -> dict[str, Any]:
    return {
        "tasks_today": 0,
        "successes_today": 0,
        "failures_today": 0,
        "last_task": None,
        "last_execution_ms": 0,
        "last_completed_at": None,
    }


def _runtime_agent_stats() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    snapshot = get_runtime_metrics().snapshot()
    stats: dict[str, dict[str, Any]] = defaultdict(_empty_agent_stat)
    for event in snapshot["events"]:
        item = stats[event["agent_name"]]
        item["tasks_today"] += 1
        if event["status"] == "success":
            item["successes_today"] += 1
        else:
            item["failures_today"] += 1
        item["last_task"] = event["task_id"]
        item["last_execution_ms"] = event["duration_ms"]
        item["last_completed_at"] = event["completed_at"].isoformat()
    return dict(stats), snapshot["active"]


async def _database_agent_stats() -> dict[str, dict[str, Any]] | None:
    from app.database import session as database_session

    if database_session.SessionLocal is None:
        return None

    from sqlalchemy import select
    from app.database.models.runtime import AgentExecution

    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    async with database_session.SessionLocal() as db:
        rows = (
            await db.execute(
                select(AgentExecution)
                .where(AgentExecution.end_time >= day_start)
                .order_by(AgentExecution.end_time.asc())
            )
        ).scalars().all()

    stats: dict[str, dict[str, Any]] = defaultdict(_empty_agent_stat)
    for row in rows:
        item = stats[row.agent_name]
        item["tasks_today"] += 1
        if row.status == "success":
            item["successes_today"] += 1
        else:
            item["failures_today"] += 1
        item["last_task"] = row.task_id
        item["last_execution_ms"] = row.duration_ms or 0
        item["last_completed_at"] = row.end_time.isoformat() if row.end_time else None
    return dict(stats)


async def get_team_status() -> dict[str, Any]:
    runtime_stats, active = _runtime_agent_stats()
    database_stats = await _database_agent_stats()
    stats = database_stats if database_stats is not None else runtime_stats

    agents: dict[str, Any] = {}
    for name, info in AGENT_REGISTRY.items():
        item = stats.get(name, _empty_agent_stat())
        running = active.get(name)
        agents[name] = {
            "display": info["display"],
            "icon": info.get("icon"),
            "status": "running" if running else "idle",
            "capabilities": info.get("capabilities", []),
            "last_task": running["task_id"] if running else item["last_task"],
            "last_execution_ms": item["last_execution_ms"],
            "tasks_today": item["tasks_today"],
            "successes_today": item["successes_today"],
            "failures_today": item["failures_today"],
            "last_completed_at": item["last_completed_at"],
        }

    total_tasks = sum(item["tasks_today"] for item in stats.values())
    success_count = sum(item["successes_today"] for item in stats.values())
    return {
        "total_agents": len(AGENT_REGISTRY),
        "online_agents": len(AGENT_REGISTRY),
        "running_agents": len(active),
        "total_tasks_today": total_tasks,
        "success_rate": round(success_count / total_tasks * 100, 1) if total_tasks else None,
        "metrics_source": "database" if database_stats is not None else "runtime",
        "agents": agents,
    }


def _empty_business_metrics() -> dict[str, Any]:
    return {
        "total_enterprises": 0,
        "total_policies": 0,
        "industry_distribution": [],
        "risk": {"high_risk": 0, "medium_risk": 0, "low_risk": 0},
        "risk_trend": [],
        "policy_updates": 0,
        "latest_risk_alerts": [],
        "data_available": False,
        "data_mode": "unavailable",
        "enterprise_data_quality": {},
        "policy_data_quality": {},
    }


def _local_file_business_metrics() -> dict[str, Any]:
    """Aggregate the read-only enterprise and policy snapshots for showcase mode."""
    metrics = _empty_business_metrics()
    try:
        from app.tools.enterprise_data import get_enterprise_data_tool

        enterprise_stats = get_enterprise_data_tool().stats()
        metrics["total_enterprises"] = int(
            enterprise_stats.get("total_enterprises") or 0
        )
        distribution = enterprise_stats.get("industry_distribution") or []
        total_with_industry = sum(int(item.get("value") or 0) for item in distribution)
        metrics["industry_distribution"] = [
            {
                "name": item.get("name") or "未分类",
                "value": int(item.get("value") or 0),
                "pct": round(int(item.get("value") or 0) / total_with_industry * 100, 1)
                if total_with_industry
                else 0,
                "color": COLORS[index % len(COLORS)],
            }
            for index, item in enumerate(distribution)
        ]
        metrics["enterprise_data_quality"] = {
            "coverage": enterprise_stats.get("coverage", {}),
            "limitations": enterprise_stats.get("limitations", []),
            "last_updated": enterprise_stats.get("last_updated"),
        }
        risk_overview = get_enterprise_data_tool().risk_overview(limit=10)
        risk_distribution = risk_overview.get("distribution") or {}
        metrics["risk"] = {
            "high_risk": int(risk_distribution.get("high") or 0),
            "medium_risk": int(risk_distribution.get("medium") or 0),
            "low_risk": int(risk_distribution.get("low") or 0),
        }
        metrics["latest_risk_alerts"] = [
            item for item in risk_overview.get("enterprises", [])
            if item.get("level") in {"high", "medium"}
        ]
    except Exception as exc:
        metrics["enterprise_data_quality"] = {"error": str(exc)}

    try:
        from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData

        policy_stats = PolicyCrawl4AIData().stats()
        metrics["total_policies"] = int(policy_stats.get("total_documents") or 0)
        metrics["policy_updates"] = int(policy_stats.get("published_today") or 0)
        metrics["policy_data_quality"] = {
            key: policy_stats.get(key)
            for key in (
                "raw_records",
                "included_records",
                "failed_records",
                "with_deadline",
                "with_funding",
                "last_updated",
            )
        }
    except Exception as exc:
        metrics["policy_data_quality"] = {"error": str(exc)}

    metrics["data_available"] = bool(
        metrics["total_enterprises"] or metrics["total_policies"]
    )
    metrics["data_mode"] = "local_snapshot" if metrics["data_available"] else "unavailable"
    return metrics


async def _database_business_metrics() -> dict[str, Any]:
    """Reuse expensive dashboard aggregates briefly across adjacent widgets."""
    from app.database import session as database_session

    if database_session.SessionLocal is None:
        return _local_file_business_metrics()

    global _BUSINESS_METRICS_CACHE
    cache_key = id(database_session.SessionLocal)
    now = monotonic()
    cached = _BUSINESS_METRICS_CACHE
    if cached and cached[0] == cache_key and now - cached[1] < _BUSINESS_METRICS_TTL_SECONDS:
        return deepcopy(cached[2])

    async with _BUSINESS_METRICS_LOCK:
        now = monotonic()
        cached = _BUSINESS_METRICS_CACHE
        if cached and cached[0] == cache_key and now - cached[1] < _BUSINESS_METRICS_TTL_SECONDS:
            return deepcopy(cached[2])
        metrics = await _load_database_business_metrics()
        _BUSINESS_METRICS_CACHE = (cache_key, now, metrics)
        return deepcopy(metrics)


async def _load_database_business_metrics() -> dict[str, Any]:
    from app.database import session as database_session

    if database_session.SessionLocal is None:
        return _local_file_business_metrics()

    from sqlalchemy import case, distinct, func, select
    from app.database.models.business import Enterprise, Industry, Policy, Risk

    metrics = _empty_business_metrics()
    async with database_session.SessionLocal() as db:
        metrics["total_enterprises"] = int(
            (await db.execute(select(func.count(Enterprise.enterprise_id)))).scalar() or 0
        )

        industry_rows = (
            await db.execute(
                select(Industry.name, func.count(Enterprise.enterprise_id))
                .select_from(Enterprise)
                .join(Industry, Enterprise.industry_id == Industry.industry_id)
                .group_by(Industry.name)
                .order_by(func.count(Enterprise.enterprise_id).desc())
                .limit(6)
            )
        ).all()
        total_with_industry = sum(int(count) for _, count in industry_rows)
        metrics["industry_distribution"] = [
            {
                "name": name,
                "value": int(count),
                "pct": round(int(count) / total_with_industry * 100, 1)
                if total_with_industry
                else 0,
                "color": COLORS[index % len(COLORS)],
            }
            for index, (name, count) in enumerate(industry_rows)
        ]

        risk_rows = (
            await db.execute(
                select(
                    func.upper(Risk.risk_level),
                    func.count(distinct(Risk.enterprise_id)),
                ).group_by(func.upper(Risk.risk_level))
            )
        ).all()
        risk_counts = {str(level or "").upper(): int(count) for level, count in risk_rows}
        metrics["risk"] = {
            "high_risk": risk_counts.get("HIGH", 0),
            "medium_risk": risk_counts.get("MEDIUM", 0),
            "low_risk": risk_counts.get("LOW", 0),
        }

        six_months_ago = datetime.utcnow() - timedelta(days=183)
        month_expr = func.date_trunc("month", Risk.created_time)
        trend_rows = (
            await db.execute(
                select(
                    month_expr.label("month"),
                    func.sum(case((func.upper(Risk.risk_level) == "HIGH", 1), else_=0)),
                    func.sum(case((func.upper(Risk.risk_level) == "MEDIUM", 1), else_=0)),
                    func.sum(case((func.upper(Risk.risk_level) == "LOW", 1), else_=0)),
                )
                .where(Risk.created_time >= six_months_ago)
                .group_by(month_expr)
                .order_by(month_expr)
            )
        ).all()
        metrics["risk_trend"] = [
            {
                "month": row[0].strftime("%Y-%m"),
                "high": int(row[1] or 0),
                "medium": int(row[2] or 0),
                "low": int(row[3] or 0),
            }
            for row in trend_rows
        ]

        metrics["policy_updates"] = int(
            (
                await db.execute(
                    select(func.count(Policy.policy_id)).where(
                        Policy.publish_date == date.today()
                    )
                )
            ).scalar()
            or 0
        )
        metrics["total_policies"] = int(
            (await db.execute(select(func.count(Policy.policy_id)))).scalar() or 0
        )

        alerts = (
            await db.execute(
                select(Risk)
                .where(func.upper(Risk.risk_level).in_(["HIGH", "MEDIUM"]))
                .order_by(Risk.created_time.desc())
                .limit(10)
            )
        ).scalars().all()
        metrics["latest_risk_alerts"] = [
            {
                "enterprise": row.enterprise_id,
                "level": (row.risk_level or "").upper(),
                "reason": row.risk_reason or row.risk_type or "未提供原因",
                "created_at": row.created_time.isoformat() if row.created_time else None,
            }
            for row in alerts
        ]
        snapshot = _local_file_business_metrics()
        snapshot_used = False
        if metrics["total_enterprises"] == 0 and snapshot["total_enterprises"] > 0:
            metrics["total_enterprises"] = snapshot["total_enterprises"]
            metrics["industry_distribution"] = snapshot["industry_distribution"]
            metrics["enterprise_data_quality"] = snapshot["enterprise_data_quality"]
            snapshot_used = True
        if metrics["total_policies"] == 0 and snapshot["total_policies"] > 0:
            metrics["total_policies"] = snapshot["total_policies"]
            metrics["policy_updates"] = snapshot["policy_updates"]
            metrics["policy_data_quality"] = snapshot["policy_data_quality"]
            snapshot_used = True
        metrics["data_available"] = bool(
            metrics["total_enterprises"]
            or metrics["total_policies"]
            or any(metrics["risk"].values())
        )
        metrics["data_mode"] = (
            "database+local_snapshot" if snapshot_used else "database"
        )
    return metrics


async def get_risk_dashboard(
    limit: int = 50, mode: str = "real"
) -> dict[str, Any]:
    """Return either persisted assessments or the isolated demo scenario."""
    if mode == "demo":
        from app.services.demo_scenario import risk_dashboard

        return risk_dashboard(limit=limit)

    business = await _database_business_metrics()
    total_enterprises = int(business["total_enterprises"])
    enterprises: list[dict[str, Any]] = []
    distribution = {"high": 0, "medium": 0, "low": 0}

    from app.database import session as database_session

    if database_session.SessionLocal is not None:
        from sqlalchemy import func, select
        from app.database.models.business import Enterprise, Risk

        ranked = (
            select(
                Risk.risk_id.label("risk_id"),
                Risk.enterprise_id.label("enterprise_id"),
                Risk.risk_score.label("risk_score"),
                Risk.risk_level.label("risk_level"),
                Risk.risk_reason.label("risk_reason"),
                Risk.risk_type.label("risk_type"),
                Risk.source.label("source"),
                Risk.created_time.label("created_time"),
                func.row_number()
                .over(
                    partition_by=Risk.enterprise_id,
                    order_by=(Risk.created_time.desc(), Risk.risk_id.desc()),
                )
                .label("row_number"),
            )
            .subquery()
        )

        async with database_session.SessionLocal() as db:
            distribution_rows = (
                await db.execute(
                    select(
                        func.upper(ranked.c.risk_level),
                        func.count(ranked.c.enterprise_id),
                    )
                    .where(ranked.c.row_number == 1)
                    .group_by(func.upper(ranked.c.risk_level))
                )
            ).all()
            for level, count in distribution_rows:
                key = str(level or "").lower()
                if key in distribution:
                    distribution[key] = int(count)

            rows = (
                await db.execute(
                    select(
                        ranked.c.risk_id,
                        ranked.c.enterprise_id,
                        Enterprise.name,
                        ranked.c.risk_score,
                        ranked.c.risk_level,
                        ranked.c.risk_reason,
                        ranked.c.risk_type,
                        ranked.c.source,
                        ranked.c.created_time,
                    )
                    .select_from(ranked)
                    .outerjoin(
                        Enterprise,
                        Enterprise.enterprise_id == ranked.c.enterprise_id,
                    )
                    .where(ranked.c.row_number == 1)
                    .order_by(
                        ranked.c.risk_score.desc().nullslast(),
                        ranked.c.created_time.desc(),
                    )
                    .limit(limit)
                )
            ).all()

        for row in rows:
            level = str(row.risk_level or "").lower()
            score = float(row.risk_score or 0)
            enterprises.append(
                {
                    "risk_id": row.risk_id,
                    "enterprise_id": row.enterprise_id,
                    "name": row.name or row.enterprise_id,
                    "score": round(score, 1),
                    "level": level,
                    "reason": row.risk_reason or row.risk_type or "未提供原因",
                    "risk_type": row.risk_type,
                    "source": row.source,
                    "created_at": (
                        row.created_time.isoformat() if row.created_time else None
                    ),
                    "trend": "stable",
                    "action": (
                        "建议尽快复核"
                        if level == "high"
                        else "持续跟踪"
                        if level == "medium"
                        else "常规监测"
                    ),
                }
            )

    evaluated = sum(distribution.values())
    risk_source = "risk table"
    if evaluated == 0:
        from app.tools.enterprise_data import get_enterprise_data_tool

        imported = get_enterprise_data_tool().risk_overview(limit=limit)
        imported_distribution = imported.get("distribution") or {}
        imported_evaluated = int(imported.get("evaluated_enterprises") or 0)
        if imported_evaluated:
            distribution = {
                key: int(imported_distribution.get(key) or 0)
                for key in ("high", "medium", "low")
            }
            enterprises = list(imported.get("enterprises") or [])
            evaluated = imported_evaluated
            risk_source = imported.get("source") or "park_document_evidence"
    data_available = evaluated > 0
    if data_available and risk_source == "park_document_evidence":
        summary = (
            f"已根据园区资料库中的可追溯公开证据识别 {evaluated} 家企业的风险事件；"
            f"其中高风险 {distribution['high']} 家、中风险 {distribution['medium']} 家。"
        )
        insights = [
            f"当前公开证据覆盖率为 "
            f"{round(evaluated / total_enterprises * 100, 1) if total_enterprises else 0}%。",
            "等级来自已导入事件的严重度映射，不是未来风险预测；需人工复核原始证据。",
        ]
    elif data_available:
        summary = (
            f"已基于 risk 表中每家企业的最新记录评估 {evaluated} 家企业，"
            f"其中高风险 {distribution['high']} 家。"
        )
        insights = [
            f"当前真实风险评估覆盖率为 "
            f"{round(evaluated / total_enterprises * 100, 1) if total_enterprises else 0}%。",
            "风险等级与排序来自数据库最新风险记录，未使用演示数据。",
        ]
    else:
        summary = (
            f"当前企业快照包含 {total_enterprises} 家企业，但 risk 表尚无真实风险评估记录。"
        )
        insights = [
            "未使用演示风险数量或虚构企业记录。",
            "导入真实风险评估后，本页会自动展示等级分布、趋势与企业明细。",
        ]

    return {
        "data_available": data_available,
        "is_demo": False,
        "disclaimer": None,
        "scenario_id": None,
        "total_enterprises": total_enterprises,
        "evaluated_enterprises": evaluated,
        "coverage_pct": (
            round(evaluated / total_enterprises * 100, 1)
            if total_enterprises
            else 0
        ),
        "distribution": distribution,
        "trend": business["risk_trend"],
        "enterprises": enterprises,
        "summary": summary,
        "insights": insights,
        "source": risk_source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_dashboard_overview(mode: str = "real") -> dict[str, Any]:
    business = await _database_business_metrics()
    team = await get_team_status()
    success_rate = team["success_rate"]
    if mode == "demo":
        from app.services.demo_scenario import (
            DEMO_DISCLAIMER,
            DEMO_FUNNEL,
            DEMO_INDUSTRIES,
            SCENARIO_ID,
            metadata as demo_metadata,
        )

        return {
            "park_overview": {
                "total_enterprises": 36,
                "growth_rate": 8.3,
            },
            "investment": {
                "opportunities": 36,
                "signed": 2,
                "conversion_rate": round(2 / 36 * 100, 1),
                "data_available": True,
                "funnel": DEMO_FUNNEL,
            },
            "policy": {
                "total": business["total_policies"],
                "published_today": business["policy_updates"],
                "data_available": business["total_policies"] > 0,
                "source": "public_snapshot",
            },
            "risk": {"high_risk": 3, "medium_risk": 8, "low_risk": 25},
            "industry_distribution": DEMO_INDUSTRIES,
            "ai_operations": {
                "agent_calls": team["total_tasks_today"],
                "success_rate": (
                    f"{success_rate}%" if success_rate is not None else None
                ),
                "running_agents": team["running_agents"],
            },
            "metadata": {
                **demo_metadata(),
                "business_data_available": True,
                "business_data_mode": "demo_scenario",
                "policy_data_mode": business["data_mode"],
                "metrics_source": team["metrics_source"],
                "unavailable_metrics": [],
                "disclaimer": DEMO_DISCLAIMER,
                "scenario_id": SCENARIO_ID,
            },
        }

    return {
        "park_overview": {
            "total_enterprises": business["total_enterprises"],
            "growth_rate": None,
        },
        "investment": {
            "opportunities": 0,
            "signed": 0,
            "conversion_rate": None,
            "data_available": False,
        },
        "policy": {
            "total": business["total_policies"],
            "published_today": business["policy_updates"],
            "data_available": business["total_policies"] > 0,
        },
        "risk": business["risk"],
        "ai_operations": {
            "agent_calls": team["total_tasks_today"],
            "success_rate": f"{success_rate}%" if success_rate is not None else None,
            "running_agents": team["running_agents"],
        },
        "metadata": {
            "presentation_mode": "real",
            "is_demo": False,
            "disclaimer": None,
            "scenario_id": None,
            "business_data_available": business["data_available"],
            "business_data_mode": business["data_mode"],
            "enterprise_data_quality": business["enterprise_data_quality"],
            "policy_data_quality": business["policy_data_quality"],
            "metrics_source": team["metrics_source"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "unavailable_metrics": [
                "park_growth_rate",
                "investment_opportunities",
                "investment_signed",
                "investment_conversion_rate",
            ],
        },
    }


async def get_bi_dashboard(mode: str = "real") -> dict[str, Any]:
    business = await _database_business_metrics()
    team = await get_team_status()
    calls = team["total_tasks_today"]
    agent_calls = [
        (name, item["tasks_today"])
        for name, item in team["agents"].items()
        if item["tasks_today"] > 0
    ]
    ai_usage = [
        {
            "agent": AGENT_REGISTRY.get(name, {}).get("display", name),
            "calls": count,
            "pct": round(count / calls * 100, 1) if calls else 0,
        }
        for name, count in sorted(agent_calls, key=lambda item: item[1], reverse=True)
    ]
    success_rate = team["success_rate"]
    crm_funnel = None
    if mode == "real":
        from app.database import session as database_session

        if database_session.SessionLocal is not None:
            from app.services.investment_crm_service import get_investment_funnel

            async with database_session.SessionLocal() as db:
                crm_funnel = await get_investment_funnel(db, data_mode="real")

    if mode == "demo":
        from app.services.demo_scenario import (
            DEMO_DISCLAIMER,
            DEMO_FUNNEL,
            DEMO_INDUSTRIES,
            DEMO_RISK_TREND,
            metadata as demo_metadata,
        )

        funnel_colors = [COLORS[0], COLORS[1], COLORS[2], "#fa8c16", "#ff4d4f"]
        investment_funnel = [
            {**item, "color": funnel_colors[index]}
            for index, item in enumerate(DEMO_FUNNEL)
        ]
        industry_total = sum(item["value"] for item in DEMO_INDUSTRIES)
        industry_distribution = [
            {
                **item,
                "pct": round(item["value"] / industry_total * 100, 1),
                "color": COLORS[index % len(COLORS)],
            }
            for index, item in enumerate(DEMO_INDUSTRIES)
        ]
        return {
            "kpi_cards": [
                {
                    "key": "enterprises",
                    "title": "示例企业总数",
                    "value": 36,
                    "unit": "家",
                    "trend": "演示场景固定基线",
                    "trend_up": True,
                    "color": COLORS[0],
                },
                {
                    "key": "investment",
                    "title": "招商目标",
                    "value": 36,
                    "unit": "项",
                    "trend": "2 家演示入驻",
                    "trend_up": True,
                    "color": COLORS[1],
                },
                {
                    "key": "risk",
                    "title": "高风险示例企业",
                    "value": 3,
                    "unit": "家",
                    "trend": "较演示基线减少 2 家",
                    "trend_up": False,
                    "color": "#ff4d4f",
                },
                {
                    "key": "ai_tasks",
                    "title": "AI 调用次数",
                    "value": calls,
                    "unit": "次/日",
                    "trend": (
                        f"成功率 {success_rate}%"
                        if success_rate is not None
                        else "今日暂无调用"
                    ),
                    "trend_up": True,
                    "color": COLORS[3],
                },
            ],
            "industry_distribution": industry_distribution,
            "investment_funnel": investment_funnel,
            "risk_trend": DEMO_RISK_TREND,
            "ai_usage": ai_usage,
            "insights": {
                "summary": DEMO_DISCLAIMER,
                "opportunities": [
                    {
                        "area": "招商推进",
                        "action": "演示场景中 5 家示例企业进入意向签约阶段。",
                    }
                ],
                "alerts": [
                    {
                        "level": "warning",
                        "msg": "3 家高风险示例企业需要进入人工复核流程。",
                    }
                ],
            },
            "metadata": {
                **demo_metadata(),
                "business_data_available": True,
                "investment_funnel_data_available": True,
                "investment_funnel_source": "demo_scenario",
                "risk_data_available": True,
                "unavailable_metrics": [],
                "metrics_source": team["metrics_source"],
            },
        }

    return {
        "kpi_cards": [
            {
                "key": "enterprises",
                "title": "园区企业总数",
                "value": business["total_enterprises"],
                "unit": "家",
                "trend": "暂无历史基线",
                "trend_up": True,
                "color": COLORS[0],
            },
            {
                "key": "investment",
                "title": "招商机会",
                "value": crm_funnel.stages[0].count if crm_funnel else None,
                "unit": "家" if crm_funnel else "",
                "trend": "来源：招商 CRM 业务事件"
                if crm_funnel
                else "业务表尚未接入",
                "trend_up": True,
                "color": COLORS[1],
            },
            {
                "key": "risk",
                "title": "高风险企业",
                "value": (
                    business["risk"]["high_risk"]
                    if any(business["risk"].values())
                    else None
                ),
                "unit": "家" if any(business["risk"].values()) else "",
                "trend": (
                    "实时风险记录"
                    if any(business["risk"].values())
                    else "尚无真实风险评估"
                ),
                "trend_up": False,
                "color": "#ff4d4f",
            },
            {
                "key": "ai_tasks",
                "title": "AI 调用次数",
                "value": calls,
                "unit": "次/日",
                "trend": f"成功率 {success_rate}%"
                if success_rate is not None
                else "今日暂无调用",
                "trend_up": True,
                "color": COLORS[3],
            },
        ],
        "industry_distribution": business["industry_distribution"],
        "investment_funnel": [
            {
                "stage": item.label,
                "count": item.count,
                "color": [
                    COLORS[0],
                    COLORS[1],
                    COLORS[2],
                    "#fa8c16",
                    "#ff4d4f",
                ][index],
            }
            for index, item in enumerate(crm_funnel.stages)
        ]
        if crm_funnel
        else [],
        "risk_trend": business["risk_trend"],
        "ai_usage": ai_usage,
        "insights": {
            "summary": "指标由当前业务库与 Agent 执行记录实时聚合，未接入的数据不再使用演示数值。",
            "opportunities": [],
            "alerts": [
                {
                    "level": "warning",
                    "msg": "尚无招商 CRM 业务事件，漏斗暂不可用。",
                }
            ]
            if crm_funnel is None
            else [],
        },
        "metadata": {
            "presentation_mode": "real",
            "is_demo": False,
            "disclaimer": None,
            "scenario_id": None,
            "business_data_available": business["data_available"],
            "investment_funnel_data_available": crm_funnel is not None,
            "investment_funnel_source": (
                crm_funnel.source if crm_funnel else None
            ),
            "risk_data_available": any(business["risk"].values()),
            "unavailable_metrics": [] if crm_funnel else ["investment_funnel"],
            "metrics_source": team["metrics_source"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


async def get_daily_report(mode: str = "real") -> dict[str, Any]:
    business = await _database_business_metrics()
    team = await get_team_status()
    now = datetime.now(timezone.utc)
    if mode == "demo":
        from app.services.demo_scenario import (
            DEMO_DISCLAIMER,
            DEMO_RISK_ENTERPRISES,
            metadata as demo_metadata,
        )

        return {
            "date": now.strftime("%Y-%m-%d"),
            "generated_at": now.isoformat(),
            "data_mode": "demo_scenario",
            "summary": DEMO_DISCLAIMER,
            "park_metrics": {
                "total_enterprises": 36,
                "active_tasks": team["running_agents"],
            },
            "investment": {
                "new_leads": 6,
                "active_negotiations": 11,
                "opportunities": 36,
                "data_available": True,
            },
            "risk_alerts": [
                {
                    "enterprise": item["name"],
                    "level": item["level"].upper(),
                    "reason": item["reason"],
                }
                for item in DEMO_RISK_ENTERPRISES[:3]
            ],
            "policy_updates": business["policy_updates"],
            "policy_total": business["total_policies"],
            "ai_tasks_completed": team["total_tasks_today"],
            "recommendations": [
                "对 3 家高风险示例企业启动人工复核。",
                "推进 5 家意向示例企业进入尽调阶段。",
            ],
            "metadata": {
                **demo_metadata(),
                "metrics_source": team["metrics_source"],
                "policy_data_mode": business["data_mode"],
            },
        }

    data_mode = business["data_mode"] if business["data_available"] else "runtime"
    return {
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "data_mode": data_mode,
        "summary": "企业与政策指标来自当前只读快照；招商漏斗和风险评估等未采集业务域标记为“待接入/尚未评估”。",
        "park_metrics": {
            "total_enterprises": business["total_enterprises"],
            "active_tasks": team["running_agents"],
        },
        "investment": {
            "new_leads": 0,
            "active_negotiations": 0,
            "opportunities": 0,
            "data_available": False,
        },
        "risk_alerts": business["latest_risk_alerts"],
        "policy_updates": business["policy_updates"],
        "policy_total": business["total_policies"],
        "ai_tasks_completed": team["total_tasks_today"],
        "recommendations": (
            ["优先接入招商机会及阶段流转业务表，才能计算真实转化率。"]
            if business["data_available"]
            else ["请检查本地企业与政策快照路径，或启用 PostgreSQL。"]
        ),
        "metadata": {
            "presentation_mode": "real",
            "is_demo": False,
            "disclaimer": None,
            "scenario_id": None,
            "metrics_source": team["metrics_source"],
            "business_data_available": business["data_available"],
            "business_data_mode": business["data_mode"],
            "enterprise_data_quality": business["enterprise_data_quality"],
            "policy_data_quality": business["policy_data_quality"],
        },
    }
