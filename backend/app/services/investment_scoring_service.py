"""Deterministic, evidence-gated scoring for investment recommendations.

The weights are product assumptions, not an objective standard.  Missing
dimensions remain ``None`` and available weights are re-normalized.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Iterable

from app.schemas.enterprise import EnterpriseProfile
from app.schemas.investment_candidate import (
    EvidenceItem,
    RecommendationCard,
    RiskAssessment,
    ScoreDimension,
)


SCORING_VERSION = "robot-investment-rules-v1.1-evidence-gated"
WEIGHTS = {
    "industry_fit": 0.30,
    "technology": 0.20,
    "growth": 0.15,
    "landing_intent": 0.10,
    "policy_fit": 0.15,
    "data_completeness": 0.10,
}

TECH_KEYWORDS = (
    "机器人",
    "工业自动化",
    "伺服",
    "驱动",
    "控制器",
    "控制系统",
    "传感器",
    "机器视觉",
    "减速器",
    "工业软件",
    "系统集成",
    "智能制造",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(profile: EnterpriseProfile) -> str:
    return " ".join(
        filter(
            None,
            (
                profile.name,
                profile.industry,
                profile.business_scope,
                profile.match_reason,
                " ".join(profile.tags),
            ),
        )
    ).lower()


def _terms(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        for term in re.split(r"[\s,，。；;、/]+", value or ""):
            normalized = term.strip().lower()
            if normalized and normalized not in output:
                output.append(normalized)
    return output


def _normalize_evidence(profile: EnterpriseProfile) -> list[EvidenceItem]:
    collected_at = profile.source_time or _now()
    snapshot_id = (
        f"{profile.data_source}-"
        f"{collected_at.strftime('%Y%m%d') if collected_at else 'unknown'}"
    )
    items: list[EvidenceItem] = []
    for index, raw in enumerate(profile.evidence, start=1):
        raw_type = str(raw.get("type") or "snapshot")
        title = str(raw.get("value") or "企业公开数据快照")
        url = str(raw.get("url") or "").strip() or None
        if profile.data_source == "demo_scenario":
            source_type = "synthetic"
        else:
            source_type = "public_web" if raw_type == "source" else "snapshot"
        items.append(
            EvidenceItem(
                id=f"{profile.enterprise_id}-e{index}",
                field="enterprise_profile",
                claim="企业画像字段来自公开来源或版本化快照",
                value=title,
                source_type=source_type,
                source_title=title,
                source_url=url,
                published_at=None,
                collected_at=collected_at,
                tool="enterprise_query",
                snapshot_id=snapshot_id,
                confidence=profile.confidence_score,
            )
        )
    return items


def _dimension(
    score: float | None,
    weight: float,
    reason: str,
    evidence_ids: list[str],
) -> ScoreDimension:
    if score is None or not evidence_ids:
        return ScoreDimension(
            score=None,
            weight=weight,
            reason=reason,
            evidence_ids=[],
        )
    return ScoreDimension(
        score=round(max(0, min(score, 100)), 1),
        weight=weight,
        reason=reason,
        evidence_ids=evidence_ids,
    )


def _chain_role(text: str, roles: list[str]) -> str:
    ranked = sorted(
        (
            (
                sum(1 for term in _terms([role]) if term in text),
                role,
            )
            for role in roles
        ),
        reverse=True,
    )
    if ranked and ranked[0][0] > 0:
        return ranked[0][1]
    return "待人工判定"


def score_enterprise(
    profile: EnterpriseProfile,
    *,
    industry: str,
    target_chain_roles: list[str],
    data_mode: str,
    weights: dict[str, float] | None = None,
) -> RecommendationCard:
    """Return a validated recommendation without treating missing values as 0."""
    active_weights = weights or WEIGHTS
    evidence = _normalize_evidence(profile)
    evidence_ids = [item.id for item in evidence]
    text = _text(profile)
    industry_terms = _terms([industry, *target_chain_roles])
    matched_industry = [term for term in industry_terms if term in text]
    matched_tech = [term for term in TECH_KEYWORDS if term.lower() in text]

    industry_score = None
    if matched_industry and evidence_ids:
        industry_score = min(95.0, 58.0 + len(matched_industry) * 9.0)

    technology_score = None
    technology_reasons: list[str] = []
    if matched_tech and evidence_ids:
        technology_score = min(92.0, 55.0 + len(matched_tech) * 7.0)
        technology_reasons.append("公开文本命中：" + "、".join(matched_tech[:5]))
    if profile.patents_count is not None and evidence_ids:
        patent_score = min(95.0, 50.0 + profile.patents_count * 2.0)
        technology_score = max(technology_score or 0, patent_score)
        technology_reasons.append(f"公开快照记录专利 {profile.patents_count} 项")

    growth_score = None
    growth_reason = "未接入可核验的融资、招聘或增长数据"
    if profile.growth_rate is not None and evidence_ids:
        growth_score = min(95.0, max(30.0, 50.0 + profile.growth_rate))
        growth_reason = "使用公开快照中的增长率字段；仍需人工核验口径"
    elif profile.funding_stage and evidence_ids:
        growth_score = 65.0
        growth_reason = "公开快照存在融资阶段字段；未据此推断融资金额"

    landing_score = None
    landing_reason = "没有权威扩产或广州落地意愿数据"
    if profile.expansion_willingness and evidence_ids:
        landing_score = 65.0
        landing_reason = "公开快照存在扩产意愿字段；需招商人员二次核验"

    completeness_fields: list[Any] = [
        profile.credit_code,
        profile.industry,
        profile.business_scope,
        profile.location,
        profile.capital_amount,
        profile.enterprise_status,
        profile.patents_count,
        profile.website,
    ]
    completeness_score = (
        round(sum(value not in (None, "", [], {}) for value in completeness_fields) / 8 * 100, 1)
        if evidence_ids
        else None
    )

    breakdown = {
        "industry_fit": _dimension(
            industry_score,
            active_weights["industry_fit"],
            (
                "命中目标产业/产业链关键词：" + "、".join(matched_industry[:5])
                if matched_industry
                else "公开画像未形成足够的目标产业匹配证据"
            ),
            evidence_ids,
        ),
        "technology": _dimension(
            technology_score,
            active_weights["technology"],
            "；".join(technology_reasons) or "缺少可核验的技术能力信号",
            evidence_ids,
        ),
        "growth": _dimension(
            growth_score,
            active_weights["growth"],
            growth_reason,
            evidence_ids,
        ),
        "landing_intent": _dimension(
            landing_score,
            active_weights["landing_intent"],
            landing_reason,
            evidence_ids,
        ),
        "policy_fit": _dimension(
            None,
            active_weights["policy_fit"],
            "仅完成产业相关检索，尚未核验具体政策申报条件",
            [],
        ),
        "data_completeness": _dimension(
            completeness_score,
            active_weights["data_completeness"],
            "按 8 个关键公开字段的非空覆盖计算，不把缺失值按 0 处理",
            evidence_ids,
        ),
    }

    # Data completeness is a quality indicator, not evidence that an
    # enterprise is a better招商 target.  It must never inflate the business
    # recommendation score.
    strategic_names = (
        "industry_fit", "technology", "growth", "landing_intent", "policy_fit",
    )
    available = [
        breakdown[name] for name in strategic_names
        if breakdown[name].score is not None
    ]
    available_weight = sum(item.weight for item in available)
    source_confidence = profile.confidence_score if evidence else 0.0
    overall_score = None
    if len(available) >= 3 and available_weight >= 0.60 and source_confidence >= 0.50:
        overall_score = round(
            sum((item.score or 0) * item.weight for item in available)
            / available_weight,
            1,
        )

    confidence = round(
        min(source_confidence, available_weight / sum(active_weights.values())),
        2,
    )
    data_status = (
        "READY" if overall_score is not None else "DATA_INSUFFICIENT"
    )

    unknown_fields = [
        name
        for name, item in (
            ("growth", breakdown["growth"]),
            ("landing_intent", breakdown["landing_intent"]),
            ("policy_fit", breakdown["policy_fit"]),
            ("risk", None),
        )
        if item is None or item.score is None
    ]
    warnings = [
        "评分权重为可配置的产品假设，不是客观或权威标准。",
        "政策“相关”不等于满足申报条件。",
        "未发现风险记录不等于低风险。",
        "数据完整度只衡量字段覆盖，不参与推荐分计算。",
    ]
    next_action = (
        "补充工商、司法、专利、融资、招聘和广州落地意愿核验"
        if unknown_fields
        else "由招商负责人复核证据并发起首次接触"
    )
    recommendation = (
        "建议进入人工复核候选池；推荐分已满足最低证据门槛，仍需人工确认。"
        if data_status == "READY"
        else "证据覆盖不足，暂不形成推荐结论；建议先补充数据。"
    )

    return RecommendationCard(
        enterprise_id=profile.enterprise_id,
        enterprise_name=profile.name,
        industry_chain_role=_chain_role(text, target_chain_roles),
        overall_score=overall_score,
        confidence=confidence,
        data_status=data_status,
        score_breakdown=breakdown,
        risk=RiskAssessment(
            level="UNKNOWN",
            score=None,
            reason="尚无该企业的真实风险评估记录",
            evidence_ids=[],
        ),
        policy_matches=[],
        recommendation=recommendation,
        next_action=next_action,
        evidence=evidence,
        unknown_fields=unknown_fields,
        warnings=warnings,
        data_mode=data_mode,
    )
