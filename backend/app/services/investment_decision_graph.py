"""Enterprise-scoped orchestration for evidence-based investment decisions.

This graph is intentionally deterministic at the aggregation boundary:
business Agents investigate and return evidence, while Python/Pydantic code
validates and merges their outputs into recommendation cards.  Natural
language generation is never allowed to alter a score, risk level, or policy
eligibility status.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.schemas.enterprise import EnterpriseProfile
from app.schemas.investment_candidate import (
    AgentOutputEnvelope,
    EnterpriseSignalItem,
    EvidenceItem,
    InvestmentDecisionRun,
    InvestmentScenarioCreate,
    PolicyMatch,
    RecommendationCard,
    RiskAssessment,
    ScoreDimension,
)
from app.services.policy_eligibility_service import evaluate_policy_conditions
from app.services.investment_scoring_service import score_enterprise


ORCHESTRATION_VERSION = "investment-decision-graph-v1.0"


class InvestmentDecisionState(TypedDict, total=False):
    request: InvestmentScenarioCreate
    profiles: list[EnterpriseProfile]
    run_id: str
    supervisor_output: AgentOutputEnvelope
    industry_output: AgentOutputEnvelope
    recommendations: list[RecommendationCard]
    warnings: list[str]
    status: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_ref(run_id: str, agent: str, enterprise_id: str | None = None) -> str:
    suffix = enterprise_id or "scenario"
    return f"{run_id}:{agent}:{suffix}"


def _as_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback or _now()


def _clamp_confidence(value: Any, default: float = 0.5) -> float:
    try:
        return round(max(0.0, min(float(value), 1.0)), 2)
    except (TypeError, ValueError):
        return default


def _industry_agent_sync(
    request: InvestmentScenarioCreate,
    run_id: str,
) -> AgentOutputEnvelope:
    started = time.perf_counter()
    try:
        from app.agents.executor import execute_business_agent

        task = {
            "task_id": _run_ref(run_id, "IndustryAgent"),
            "agent": "IndustryAgent",
            "intent": "industry_chain",
            "priority": "high",
            "input": {
                "query": " ".join(
                    [request.industry, *request.target_chain_roles]
                ),
                "industry": request.industry,
                "region": request.location_preference or "广州",
                "data_mode": request.data_mode,
            },
        }
        raw = execute_business_agent(
            "IndustryAgent",
            task,
            {"agent_results": {}},
        )
        payload = raw.get("result", {}).get("data", {})
        evidence_level = payload.get("evidence_level") or "insufficient"
        insufficient = evidence_level == "insufficient"
        partial = evidence_level == "partial"
        return AgentOutputEnvelope(
            agent="IndustryAgent",
            status="DATA_INSUFFICIENT" if insufficient else "SUCCESS",
            result=payload,
            unknown_fields=(
                ["industry_chain_evidence", "market_trend"]
                if insufficient
                else (["market_trend", "market_size"] if partial else [])
            ),
            warnings=(
                ["产业链专题数据不足，当前只保留招商场景输入作为筛选约束"]
                if insufficient
                else (["产业链结果仅反映公开企业快照覆盖，不代表市场份额或真实产业缺口"] if partial else [])
            ),
            tools_used=raw.get("trace", {}).get("tools_used", []),
            data_sources=raw.get("trace", {}).get("data_sources", []),
            run_ref=_run_ref(run_id, "IndustryAgent"),
            execution_time_ms=raw.get(
                "execution_time_ms",
                int((time.perf_counter() - started) * 1000),
            ),
        )
    except Exception as exc:
        return AgentOutputEnvelope(
            agent="IndustryAgent",
            status="FAILED",
            result={},
            unknown_fields=["industry_chain_evidence", "market_trend"],
            warnings=[f"Industry Agent 执行失败：{type(exc).__name__}"],
            run_ref=_run_ref(run_id, "IndustryAgent"),
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )


def _investment_envelope(
    profile: EnterpriseProfile,
    card: RecommendationCard,
    run_id: str,
) -> AgentOutputEnvelope:
    evidence_ids = [item.id for item in card.evidence]
    return AgentOutputEnvelope(
        agent="InvestmentAgent",
        enterprise_id=profile.enterprise_id,
        status="SUCCESS" if evidence_ids else "DATA_INSUFFICIENT",
        result={
            "enterprise_name": profile.name,
            "industry": profile.industry,
            "location": profile.location,
            "industry_chain_role": card.industry_chain_role,
            "match_reason": profile.match_reason,
            "data_source": profile.data_source,
        },
        evidence_ids=evidence_ids,
        unknown_fields=[] if evidence_ids else ["enterprise_profile"],
        warnings=[] if evidence_ids else ["企业画像没有可追溯证据"],
        tools_used=["enterprise_search", "enterprise_profile_get"],
        data_sources=[profile.data_source],
        run_ref=_run_ref(run_id, "InvestmentAgent", profile.enterprise_id),
    )


def _enterprise_data_envelope(
    profile: EnterpriseProfile,
    card: RecommendationCard,
    run_id: str,
) -> AgentOutputEnvelope:
    """Normalize growth/finance/employment/landing fields without inventing data."""

    evidence_ids = [item.id for item in card.evidence]
    as_of_date = profile.source_time or _now()
    confidence = profile.confidence_score if evidence_ids else 0.0
    raw_signals = {
        "growth_rate": (
            profile.growth_rate,
            "公开快照中的增长率；仍需核验统计口径",
        ),
        "funding_stage": (
            profile.funding_stage,
            "公开快照中的融资阶段；不据此推断融资金额",
        ),
        "funding_amount": (
            profile.funding_amount,
            "公开快照中的融资金额字段",
        ),
        "employee_count": (
            profile.employee_count,
            "参保或员工规模，不等于招聘趋势",
        ),
        "recruitment_trend": (
            None,
            "尚未接入版本化招聘职位时间序列",
        ),
        "patents_count": (
            profile.patents_count,
            "公开快照中的专利数量字段",
        ),
        "expansion_willingness": (
            profile.expansion_willingness,
            "扩产或落地意愿仍需招商人员二次确认",
        ),
    }
    signals: list[EnterpriseSignalItem] = []
    unknown_fields: list[str] = []
    for field, (value, note) in raw_signals.items():
        available = value not in (None, "", [], {})
        status = "AVAILABLE" if available and evidence_ids else "UNKNOWN"
        if field == "expansion_willingness" and available and evidence_ids:
            status = "NEEDS_VERIFICATION"
        if status == "UNKNOWN":
            unknown_fields.append(field)
        signals.append(
            EnterpriseSignalItem(
                field=field,
                value=value if available else None,
                status=status,
                evidence_ids=evidence_ids if status != "UNKNOWN" else [],
                as_of_date=as_of_date if status != "UNKNOWN" else None,
                confidence=confidence if status != "UNKNOWN" else 0.0,
                note=note,
            )
        )

    available_count = sum(item.status != "UNKNOWN" for item in signals)
    coverage = round(available_count / len(signals), 2) if signals else 0.0
    warnings = [
        "招聘趋势尚未接入；员工规模不能替代招聘增长信号"
    ]
    if any(item.field == "expansion_willingness" and item.value for item in signals):
        warnings.append("公开扩产信号不等于企业已确认广州落地意愿")
    return AgentOutputEnvelope(
        agent="EnterpriseData",
        enterprise_id=profile.enterprise_id,
        status="SUCCESS" if available_count else "DATA_INSUFFICIENT",
        result={
            "signals": [item.model_dump(mode="json") for item in signals],
            "coverage": coverage,
            "available_count": available_count,
            "total_count": len(signals),
        },
        evidence_ids=evidence_ids,
        unknown_fields=unknown_fields,
        warnings=warnings,
        tools_used=["enterprise_profile_get"],
        data_sources=[profile.data_source],
        run_ref=_run_ref(run_id, "EnterpriseData", profile.enterprise_id),
    )


DEMO_RISK_MAP: dict[str, dict[str, Any]] = {
    "DEMO-TARGET-001": {"level": "LOW", "score": 28, "reason": "演示：企业近三年无重大诉讼或行政处罚，回款周期稳定", "action": "保持常规监测"},
    "DEMO-TARGET-002": {"level": "LOW", "score": 32, "reason": "演示：主要客户为行业头部企业，订单结构健康", "action": "关注大客户集中度变化"},
    "DEMO-TARGET-003": {"level": "MEDIUM", "score": 55, "reason": "演示：关键零部件进口占比偏高，供应链存在单一来源风险", "action": "建议评估国产替代方案"},
    "DEMO-TARGET-004": {"level": "MEDIUM", "score": 48, "reason": "演示：A轮早期企业，研发费用高，经营性现金流为负", "action": "核验融资到账情况和研发转化进度"},
    "DEMO-TARGET-005": {"level": "LOW", "score": 25, "reason": "演示：已有稳定客户基础，产品交付周期正常", "action": "保持常规监测"},
}


def _demo_risk_for(enterprise_id: str, _name: str, _industry: str | None) -> dict[str, Any]:
    if enterprise_id in DEMO_RISK_MAP:
        return DEMO_RISK_MAP[enterprise_id]
    return {"level": "LOW", "score": 20, "reason": "演示数据：未发现显著风险信号", "action": "保持常规监测"}


def _risk_agent_sync(
    profile: EnterpriseProfile,
    data_mode: str,
    run_id: str,
) -> tuple[AgentOutputEnvelope, list[EvidenceItem], RiskAssessment]:
    started = time.perf_counter()
    run_ref = _run_ref(run_id, "RiskAgent", profile.enterprise_id)
    if data_mode == "demo":
        demo_risk = _demo_risk_for(profile.enterprise_id, profile.name, profile.industry)
        envelope = AgentOutputEnvelope(
            agent="RiskAgent",
            enterprise_id=profile.enterprise_id,
            status="SUCCESS",
            result={
                "risk_level": demo_risk["level"],
                "risk_score": demo_risk["score"],
                "risk_reason": demo_risk["reason"],
                "action": demo_risk["action"],
            },
            evidence_ids=["DEMO-EVIDENCE-RISK-001"],
            data_sources=["demo_scenario"],
            run_ref=run_ref,
        )
        return (
            envelope,
            [
                EvidenceItem(
                    id="DEMO-EVIDENCE-RISK-001",
                    field="risk",
                    claim=demo_risk["reason"],
                    value=demo_risk["level"],
                    source_type="synthetic",
                    source_title="演示沙盘风险评估",
                    source_url="",
                    collected_at=datetime.now(timezone.utc).isoformat(),
                    tool="demo_scenario",
                    snapshot_id="demo-scenario-v1",
                    confidence=0.80,
                )
            ],
            RiskAssessment(
                level=demo_risk["level"],
                score=demo_risk["score"],
                reason=demo_risk["reason"],
                evidence_ids=["DEMO-EVIDENCE-RISK-001"],
            ),
        )

    try:
        from app.langgraph.nodes.risk_nodes import get_risk_graph

        raw = get_risk_graph().invoke(
            {
                "task_id": run_ref,
                "intent": "risk_single",
                "input": {
                    "enterprise_id": profile.enterprise_id,
                    "data_mode": data_mode,
                },
                "enterprise_id": profile.enterprise_id,
                "status": "idle",
                "tools_used": [],
                "data_sources": [],
            }
        )
        events = [
            item for item in (raw.get("risk_events") or [])
            if isinstance(item, dict)
        ]
        evidence: list[EvidenceItem] = []
        for index, event in enumerate(events, start=1):
            event_id = str(event.get("event_id") or index)
            source_time = _as_datetime(
                event.get("source_time"),
                profile.source_time or _now(),
            )
            evidence.append(
                EvidenceItem(
                    id=f"{profile.enterprise_id}-risk-{event_id}",
                    field="risk",
                    claim=str(
                        event.get("title")
                        or event.get("description")
                        or "企业风险事件"
                    ),
                    value={
                        "event_type": event.get("event_type"),
                        "event_level": event.get("event_level"),
                        "occurred_date": event.get("occurred_date"),
                    },
                    source_type=str(
                        event.get("data_source") or "risk_event_snapshot"
                    ),
                    source_title=str(
                        event.get("source") or event.get("title") or "风险事件来源"
                    ),
                    source_url=event.get("source_url") or None,
                    published_at=None,
                    collected_at=source_time,
                    tool="enterprise_risk_events",
                    snapshot_id=f"risk-{profile.enterprise_id}-{source_time:%Y%m%d}",
                    confidence=_clamp_confidence(
                        event.get("confidence_score"),
                        0.7,
                    ),
                )
            )

        if evidence:
            severity = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
            highest = max(
                (
                    str(event.get("event_level") or "MEDIUM").upper()
                    for event in events
                ),
                key=lambda value: severity.get(value, 2),
            )
            if highest not in severity:
                highest = "MEDIUM"
            score = {"LOW": 25.0, "MEDIUM": 60.0, "HIGH": 85.0}[highest]
            assessment = RiskAssessment(
                level=highest,
                score=score,
                reason=f"Risk Agent 核验到 {len(evidence)} 条风险事件，最高等级 {highest}",
                evidence_ids=[item.id for item in evidence],
            )
            status = "SUCCESS"
            unknown_fields: list[str] = []
            warnings = [
                "风险等级按已核验事件的最高等级汇总，不代表全面尽调结论"
            ]
        else:
            assessment = RiskAssessment(
                level="UNKNOWN",
                score=None,
                reason="Risk Agent 未取得可核验的企业风险事件",
                evidence_ids=[],
            )
            status = "DATA_INSUFFICIENT"
            unknown_fields = ["risk"]
            warnings = ["未发现记录不等于低风险；当前风险结论保持 UNKNOWN"]

        envelope = AgentOutputEnvelope(
            agent="RiskAgent",
            enterprise_id=profile.enterprise_id,
            status=status,
            result={
                "risk_score": assessment.score,
                "risk_level": assessment.level,
                "reason": assessment.reason,
                "event_count": len(events),
                "agent_report": raw.get("report", {}),
            },
            evidence_ids=assessment.evidence_ids,
            unknown_fields=unknown_fields,
            warnings=warnings,
            tools_used=raw.get("tools_used", []),
            data_sources=raw.get("data_sources", []),
            run_ref=run_ref,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )
        return envelope, evidence, assessment
    except Exception as exc:
        envelope = AgentOutputEnvelope(
            agent="RiskAgent",
            enterprise_id=profile.enterprise_id,
            status="FAILED",
            result={},
            unknown_fields=["risk"],
            warnings=[f"Risk Agent 执行失败：{type(exc).__name__}"],
            run_ref=run_ref,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )
        return (
            envelope,
            [],
            RiskAssessment(
                level="UNKNOWN",
                score=None,
                reason="Risk Agent 执行失败，风险保持 UNKNOWN",
                evidence_ids=[],
            ),
        )


def _policy_agent_sync(
    profile: EnterpriseProfile,
    request: InvestmentScenarioCreate,
    run_id: str,
    enterprise_evidence_ids: list[str],
) -> tuple[AgentOutputEnvelope, list[EvidenceItem], list[PolicyMatch]]:
    started = time.perf_counter()
    run_ref = _run_ref(run_id, "PolicyAgent", profile.enterprise_id)
    try:
        from app.langgraph.nodes.policy_nodes import get_policy_graph

        query = " ".join(
            filter(
                None,
                [
                    request.industry,
                    profile.industry,
                    *request.target_chain_roles,
                    profile.location,
                ],
            )
        )
        input_payload: dict[str, Any] = {
            "query": query,
            "data_mode": request.data_mode,
        }
        if request.data_mode == "real":
            input_payload["enterprise_id"] = profile.enterprise_id

        raw = get_policy_graph().invoke(
            {
                "task_id": run_ref,
                "intent": "policy_match",
                "input": input_payload,
                "status": "idle",
                "tools_used": [],
                "data_sources": [],
            }
        )
        report = raw.get("report", {})
        policies = [
            item for item in (report.get("policies") or [])
            if isinstance(item, dict)
        ][:10]
        evidence: list[EvidenceItem] = []
        matches: list[PolicyMatch] = []
        collected_at = _now()
        for index, policy in enumerate(policies, start=1):
            policy_id = str(policy.get("policy_id") or f"match-{index}")
            evidence_id = f"{profile.enterprise_id}-policy-{policy_id}"
            score = policy.get("match_score")
            confidence = _clamp_confidence(
                (float(score) / 100.0) if score is not None else None,
                0.6,
            )
            evidence.append(
                EvidenceItem(
                    id=evidence_id,
                    field="policy_related",
                    claim="政策与企业产业、地区或经营画像相关",
                    value={
                        "title": policy.get("title"),
                        "match_score": score,
                        "content_snippet": policy.get("content_snippet"),
                    },
                    source_type="policy_public_snapshot",
                    source_title=str(policy.get("title") or "政策公开快照"),
                    source_url=policy.get("source_url") or None,
                    published_at=None,
                    collected_at=collected_at,
                    tool="policy_hybrid_search",
                    snapshot_id=f"policy-{policy_id}",
                    confidence=confidence,
                )
            )
            eligibility, condition_results, eligibility_reason = (
                evaluate_policy_conditions(
                    profile,
                    [
                        item
                        for item in (policy.get("requirements") or [])
                        if isinstance(item, dict)
                    ],
                    enterprise_evidence_ids=enterprise_evidence_ids,
                    policy_evidence_id=evidence_id,
                )
            )
            matches.append(
                PolicyMatch(
                    policy_id=policy_id,
                    title=str(policy.get("title") or "未命名政策"),
                    match_type=eligibility,
                    reason=eligibility_reason,
                    match_score=(
                        float(score) if score is not None else None
                    ),
                    matched_terms=[
                        str(term)
                        for term in (policy.get("matched_terms") or [])
                        if str(term).strip()
                    ],
                    source_type=str(policy.get("source_type") or "public_policy"),
                    source_title=policy.get("source_title") or None,
                    source_url=policy.get("source_url") or None,
                    evidence_ids=list(
                        dict.fromkeys(
                            [
                                evidence_id,
                                *[
                                    condition_evidence_id
                                    for condition in condition_results
                                    for condition_evidence_id in condition.evidence_ids
                                ],
                            ]
                        )
                    ),
                    condition_results=condition_results,
                )
            )

        status = "SUCCESS" if matches else "DATA_INSUFFICIENT"
        eligibility_known = any(
            item.match_type in {"ELIGIBLE", "INELIGIBLE"}
            for item in matches
        )
        envelope = AgentOutputEnvelope(
            agent="PolicyAgent",
            enterprise_id=profile.enterprise_id,
            status=status,
            result={
                "total_matched": len(matches),
                "search_mode": report.get("search_mode"),
                "policies": [
                    {
                        "policy_id": item.policy_id,
                        "title": item.title,
                        "match_type": item.match_type,
                        "match_score": item.match_score,
                        "matched_terms": item.matched_terms,
                        "source_type": item.source_type,
                        "source_title": item.source_title,
                        "source_url": item.source_url,
                        "condition_results": [
                            condition.model_dump(mode="json")
                            for condition in item.condition_results
                        ],
                    }
                    for item in matches
                ],
            },
            evidence_ids=[item.id for item in evidence],
            unknown_fields=[] if eligibility_known else ["policy_eligibility"],
            warnings=[
                "仅当全部已复核强制条件均有企业证据支持时，才标记 ELIGIBLE"
            ],
            tools_used=raw.get("tools_used", []),
            data_sources=raw.get("data_sources", []),
            run_ref=run_ref,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )
        return envelope, evidence, matches
    except Exception as exc:
        envelope = AgentOutputEnvelope(
            agent="PolicyAgent",
            enterprise_id=profile.enterprise_id,
            status="FAILED",
            result={},
            unknown_fields=["policy_fit", "policy_eligibility"],
            warnings=[f"Policy Agent 执行失败：{type(exc).__name__}"],
            run_ref=run_ref,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
        )
        return envelope, [], []


async def _evaluate_profile(
    profile: EnterpriseProfile,
    request: InvestmentScenarioCreate,
    run_id: str,
    supervisor_output: AgentOutputEnvelope,
    industry_output: AgentOutputEnvelope,
) -> RecommendationCard:
    base_card = score_enterprise(
        profile,
        industry=request.industry,
        target_chain_roles=request.target_chain_roles,
        data_mode=request.data_mode,
        weights=request.weights,
    )
    investment_output = _investment_envelope(profile, base_card, run_id)
    enterprise_data_output = _enterprise_data_envelope(
        profile,
        base_card,
        run_id,
    )
    risk_result, policy_result = await asyncio.gather(
        asyncio.to_thread(
            _risk_agent_sync,
            profile,
            request.data_mode,
            run_id,
        ),
        asyncio.to_thread(
            _policy_agent_sync,
            profile,
            request,
            run_id,
            [item.id for item in base_card.evidence],
        ),
    )
    risk_output, risk_evidence, risk_assessment = risk_result
    policy_output, policy_evidence, policy_matches = policy_result

    policy_score: float | None = None
    policy_reason = "Policy Agent 仅确认政策相关性，申报资格仍需补证"
    policy_score_evidence: list[str] = []
    eligible_matches = [
        item for item in policy_matches
        if item.match_type == "ELIGIBLE"
    ]
    ineligible_matches = [
        item for item in policy_matches
        if item.match_type == "INELIGIBLE"
    ]
    # Collect all individual condition results across all policies
    all_conditions = [
        c for item in policy_matches
        for c in (item.condition_results or [])
        if c.status in ("SATISFIED", "UNSATISFIED")
    ]
    satisfied_count = sum(1 for c in all_conditions if c.status == "SATISFIED")
    total_reviewed = len(all_conditions)

    if eligible_matches:
        policy_score = 90.0
        policy_reason = (
            f"{len(eligible_matches)} 条政策的全部已复核强制条件有证据支持"
        )
        policy_score_evidence = list(
            dict.fromkeys(
                evidence_id
                for item in eligible_matches
                for evidence_id in item.evidence_ids
            )
        )
    elif ineligible_matches and len(ineligible_matches) == len(policy_matches):
        policy_score = 20.0
        policy_reason = "已核验政策均存在明确不满足的强制条件"
        policy_score_evidence = list(
            dict.fromkeys(
                evidence_id
                for item in ineligible_matches
                for evidence_id in item.evidence_ids
            )
        )
    elif total_reviewed > 0:
        # Proportional score based on satisfied ratio among reviewed conditions
        ratio = satisfied_count / total_reviewed
        policy_score = round(25.0 + ratio * 65.0, 1)  # range: 25~90
        satisfied_policies = len({
            item.policy_id
            for item in policy_matches
            for c in (item.condition_results or [])
            if c.status == "SATISFIED"
        })
        policy_reason = (
            f"{len(policy_matches)} 条政策相关，已复核 {total_reviewed} 个条件"
            f"（{satisfied_count} 满足 / {total_reviewed - satisfied_count} 不满足），"
            f"涉及 {satisfied_policies} 条政策存在满足项"
        )
        policy_score_evidence = list(
            dict.fromkeys(
                evidence_id
                for item in policy_matches
                for evidence_id in item.evidence_ids
            )
        )

    score_breakdown = dict(base_card.score_breakdown)
    if policy_score is not None and policy_score_evidence:
        score_breakdown["policy_fit"] = ScoreDimension(
            score=policy_score,
            weight=score_breakdown["policy_fit"].weight,
            reason=policy_reason,
            evidence_ids=policy_score_evidence,
        )
    strategic_names = (
        "industry_fit", "technology", "growth", "landing_intent", "policy_fit",
    )
    available_dimensions = [
        score_breakdown[name] for name in strategic_names
        if score_breakdown[name].score is not None
    ]
    available_weight = sum(item.weight for item in available_dimensions)
    overall_score = (
        round(
            sum(item.score * item.weight for item in available_dimensions)
            / available_weight,
            1,
        )
        if (
            len(available_dimensions) >= 3
            and available_weight >= 0.60
            and profile.confidence_score >= 0.50
        )
        else None
    )
    confidence = round(
        min(
            profile.confidence_score if base_card.evidence else 0.0,
            available_weight,
        ),
        2,
    )

    evidence_by_id = {item.id: item for item in base_card.evidence}
    for item in [*risk_evidence, *policy_evidence]:
        evidence_by_id[item.id] = item

    unknown_fields = list(base_card.unknown_fields)
    if risk_assessment.level != "UNKNOWN" and "risk" in unknown_fields:
        unknown_fields.remove("risk")
    if policy_score is not None and "policy_fit" in unknown_fields:
        unknown_fields.remove("policy_fit")
    for field in [
        *industry_output.unknown_fields,
        *investment_output.unknown_fields,
        *enterprise_data_output.unknown_fields,
        *risk_output.unknown_fields,
        *policy_output.unknown_fields,
    ]:
        if field not in unknown_fields:
            unknown_fields.append(field)

    warnings: list[str] = []
    for warning in [
        *base_card.warnings,
        *industry_output.warnings,
        *enterprise_data_output.warnings,
        *risk_output.warnings,
        *policy_output.warnings,
    ]:
        if warning and warning not in warnings:
            warnings.append(warning)

    agent_outputs = {
        "Supervisor": supervisor_output,
        "IndustryAgent": industry_output,
        "InvestmentAgent": investment_output,
        "EnterpriseData": enterprise_data_output,
        "RiskAgent": risk_output,
        "PolicyAgent": policy_output,
    }
    trace_refs = {
        key: value.run_ref
        for key, value in agent_outputs.items()
        if value.run_ref
    }
    data_status = "READY" if overall_score is not None else "DATA_INSUFFICIENT"
    recommendation = (
        "建议进入人工复核候选池；推荐分已满足最低证据门槛，仍需人工确认。"
        if data_status == "READY"
        else "证据覆盖不足，暂不生成推荐分；可作为相关企业线索继续补证。"
    )
    return base_card.model_copy(
        update={
            "risk": risk_assessment,
            "policy_matches": policy_matches,
            "score_breakdown": score_breakdown,
            "overall_score": overall_score,
            "confidence": confidence,
            "data_status": data_status,
            "recommendation": recommendation,
            "evidence": list(evidence_by_id.values()),
            "unknown_fields": unknown_fields,
            "warnings": warnings,
            "agent_outputs": agent_outputs,
            "trace_refs": trace_refs,
        }
    )


def _supervisor_node(
    state: InvestmentDecisionState,
) -> InvestmentDecisionState:
    request = state["request"]
    run_id = state["run_id"]
    state["status"] = "SUPERVISOR_PLANNING"
    state["supervisor_output"] = AgentOutputEnvelope(
        agent="Supervisor",
        status="SUCCESS",
        result={
            "scenario": {
                "name": request.name,
                "industry": request.industry,
                "target_chain_roles": request.target_chain_roles,
                "location_preference": request.location_preference,
                "data_mode": request.data_mode,
            },
            "task_plan": [
                {
                    "step": "industry_context",
                    "agent": "IndustryAgent",
                    "scope": "scenario",
                },
                {
                    "step": "enterprise_recall",
                    "agent": "InvestmentAgent",
                    "scope": "enterprise",
                },
                {
                    "step": "enterprise_evidence_enrichment",
                    "agent": "EnterpriseData",
                    "scope": "enterprise",
                },
                {
                    "step": "risk_verification",
                    "agent": "RiskAgent",
                    "scope": "enterprise",
                },
                {
                    "step": "policy_condition_verification",
                    "agent": "PolicyAgent",
                    "scope": "enterprise",
                },
                {
                    "step": "deterministic_aggregation",
                    "agent": "RuleAggregator",
                    "scope": "enterprise",
                },
            ],
            "guardrails": {
                "agent_can_modify_score": False,
                "agent_can_modify_risk_level": False,
                "agent_can_modify_policy_eligibility": False,
                "missing_data_is_zero": False,
            },
        },
        run_ref=_run_ref(run_id, "Supervisor"),
    )
    return state


async def _industry_node(
    state: InvestmentDecisionState,
) -> InvestmentDecisionState:
    state["status"] = "INDUSTRY_ANALYSIS"
    state["industry_output"] = await asyncio.to_thread(
        _industry_agent_sync,
        state["request"],
        state["run_id"],
    )
    return state


async def _enterprise_fanout_node(
    state: InvestmentDecisionState,
) -> InvestmentDecisionState:
    state["status"] = "ENTERPRISE_AGENT_FANOUT"
    cards = await asyncio.gather(
        *[
            _evaluate_profile(
                profile,
                state["request"],
                state["run_id"],
                state["supervisor_output"],
                state["industry_output"],
            )
            for profile in state["profiles"]
        ]
    )
    state["recommendations"] = list(cards)
    return state


def _aggregate_node(
    state: InvestmentDecisionState,
) -> InvestmentDecisionState:
    state["recommendations"] = sorted(
        state.get("recommendations", []),
        key=lambda item: (
            item.data_status == "READY",
            item.overall_score is not None,
            item.overall_score or -1,
            item.confidence or -1,
        ),
        reverse=True,
    )[: state["request"].limit]
    state["warnings"] = sorted(
        {
            warning
            for card in state["recommendations"]
            for warning in card.warnings
        }
    )
    state["status"] = "READY"
    return state


def build_investment_decision_graph():
    workflow = StateGraph(InvestmentDecisionState)
    workflow.add_node("supervisor", _supervisor_node)
    workflow.add_node("industry", _industry_node)
    workflow.add_node("enterprise_fanout", _enterprise_fanout_node)
    workflow.add_node("aggregate", _aggregate_node)
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "industry")
    workflow.add_edge("industry", "enterprise_fanout")
    workflow.add_edge("enterprise_fanout", "aggregate")
    workflow.add_edge("aggregate", END)
    return workflow.compile()


_decision_graph = None


def get_investment_decision_graph():
    global _decision_graph
    if _decision_graph is None:
        _decision_graph = build_investment_decision_graph()
    return _decision_graph


async def run_investment_decision(
    request: InvestmentScenarioCreate,
    profiles: list[EnterpriseProfile],
) -> InvestmentDecisionRun:
    run_id = f"investment-{uuid4()}"
    result = await get_investment_decision_graph().ainvoke(
        {
            "request": request,
            "profiles": profiles,
            "run_id": run_id,
            "warnings": [],
            "status": "PENDING",
        }
    )
    return InvestmentDecisionRun(
        run_id=run_id,
        version=ORCHESTRATION_VERSION,
        generated_at=_now(),
        supervisor_output=result["supervisor_output"],
        industry_output=result["industry_output"],
        recommendations=result.get("recommendations", []),
        warnings=result.get("warnings", []),
    )
