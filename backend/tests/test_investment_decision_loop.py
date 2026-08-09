from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.langgraph.nodes.bi_nodes import get_bi_graph
from app.main import app
from app.database.models.investment import (
    CandidateAudit,
    InvestmentCandidate,
    InvestmentScenario,
)
from app.schemas.enterprise import EnterpriseProfile
from app.schemas.investment_candidate import (
    AgentOutputEnvelope,
    CandidateCreate,
    EvidenceItem,
    InvestmentScenarioCreate,
    PolicyMatch,
    RiskAssessment,
)
from app.services.investment_candidate_service import create_candidate
from app.services.investment_decision_graph import run_investment_decision
from app.services.investment_evaluation_service import _profiles
from app.services.investment_scoring_service import score_enterprise
from app.services.policy_eligibility_service import evaluate_policy_conditions


ENTERPRISE_SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "enterprises"
    / "enterprise_import_clean.json"
)


def _profile(*, with_evidence: bool = True) -> EnterpriseProfile:
    return EnterpriseProfile(
        enterprise_id="ENT-ROBOT-001",
        name="广州某机器人技术有限公司",
        industry="机器人",
        business_scope="工业机器人控制系统、伺服驱动与系统集成",
        location="广州",
        enterprise_status="存续",
        capital_amount=1000,
        patents_count=None,
        data_source="local_json",
        source_time=datetime(2026, 7, 30, tzinfo=timezone.utc),
        confidence_score=0.82,
        evidence=(
            [
                {
                    "type": "source",
                    "value": "企业公开信息页",
                    "url": "https://example.com/enterprise",
                },
                {
                    "type": "snapshot",
                    "value": "enterprise-snapshot.json",
                    "url": "",
                },
            ]
            if with_evidence
            else []
        ),
    )


def test_scoring_keeps_missing_dimensions_null_and_evidence_linked():
    card = score_enterprise(
        _profile(),
        industry="机器人",
        target_chain_roles=["核心零部件", "系统集成", "工业软件"],
        data_mode="real",
    )

    assert card.data_status == "DATA_INSUFFICIENT"
    assert card.overall_score is None
    assert card.score_breakdown["industry_fit"].score is not None
    assert card.score_breakdown["growth"].score is None
    assert card.score_breakdown["landing_intent"].score is None
    assert card.score_breakdown["policy_fit"].score is None
    assert card.risk.level == "UNKNOWN"
    assert card.risk.score is None
    assert card.evidence
    assert card.score_breakdown["industry_fit"].evidence_ids
    assert "policy_fit" in card.unknown_fields


def test_scoring_without_evidence_does_not_create_a_zero_score():
    card = score_enterprise(
        _profile(with_evidence=False),
        industry="机器人",
        target_chain_roles=["系统集成"],
        data_mode="real",
    )

    assert card.data_status == "DATA_INSUFFICIENT"
    assert card.overall_score is None
    assert all(item.score is None for item in card.score_breakdown.values())
    assert card.confidence == 0


def test_policy_eligibility_requires_reviewed_conditions_and_enterprise_evidence():
    profile = _profile()
    status, conditions, reason = evaluate_policy_conditions(
        profile,
        [
            {
                "condition_code": "REGISTERED_REGION",
                "label": "注册地在广州",
                "field": "region",
                "operator": "IN",
                "expected_value": ["广州"],
                "mandatory": True,
                "review_status": "REVIEWED",
                "source_text": "申报单位须在广州市依法登记注册",
            }
        ],
        enterprise_evidence_ids=["enterprise-e1"],
        policy_evidence_id="policy-e1",
    )

    assert status == "ELIGIBLE"
    assert conditions[0].status == "SATISFIED"
    assert conditions[0].evidence_ids == ["policy-e1", "enterprise-e1"]
    assert "强制条件" in reason

    unreviewed_status, unreviewed, _ = evaluate_policy_conditions(
        profile,
        [
            {
                "condition_code": "R_AND_D_RATIO",
                "field": "unsupported_ratio",
                "operator": "GTE",
                "expected_value": 3,
                "review_status": "DRAFT",
            }
        ],
        enterprise_evidence_ids=["enterprise-e1"],
        policy_evidence_id="policy-e1",
    )
    assert unreviewed_status == "UNKNOWN"
    assert unreviewed[0].status == "NEEDS_MANUAL_REVIEW"


def test_public_bi_agent_never_returns_historical_demo_metrics():
    result = get_bi_graph().invoke(
        {
            "task_id": "test-bi-real",
            "intent": "dashboard_kpi",
            "input": {"data_mode": "real", "dashboard_type": "overview"},
            "status": "idle",
        }
    )

    assert result["data_mode"] == "real"
    assert result["kpi_result"]["park_overview"]["total_enterprises"] is None
    assert result["kpi_result"]["investment"]["opportunities"] is None
    assert result["kpi_result"]["investment"]["signed"] is None
    assert result["kpi_result"]["investment"]["conversion_rate"] is None
    assert result["kpi_result"]["risk"]["risk_level"] == "UNKNOWN"
    assert result["dashboard_result"]["cards"][0]["value"] is None
    assert "未接入" in result["insight_result"]["summary"]


def test_demo_bi_agent_reads_the_isolated_demo_scenario():
    result = get_bi_graph().invoke(
        {
            "task_id": "test-bi-demo",
            "intent": "dashboard_kpi",
            "input": {"data_mode": "demo", "dashboard_type": "overview"},
            "status": "idle",
        }
    )

    assert result["data_mode"] == "demo"
    assert result["kpi_result"]["park_overview"]["total_enterprises"] == 36
    assert result["kpi_result"]["investment"]["signed"] == 2
    assert "演示沙盘" in result["insight_result"]["summary"]


def test_candidate_persistence_reports_database_requirement_in_local_mode():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/investment/scenarios",
            json={
                "name": "广州机器人产业园招商",
                "industry": "机器人",
                "target_chain_roles": ["核心零部件", "系统集成"],
                "location_preference": "广州",
                "limit": 5,
                "data_mode": "real",
            },
        )

    assert response.status_code == 503
    assert "DATABASE_ENABLED=true" in response.json()["detail"]


@pytest.mark.skipif(
    not ENTERPRISE_SNAPSHOT.is_file(),
    reason="optional enterprise snapshot is not distributed with the source release",
)
@pytest.mark.asyncio
async def test_real_mode_recall_uses_the_public_snapshot_and_validated_cards():
    request = InvestmentScenarioCreate(
        name="广州机器人产业园招商",
        industry="机器人",
        target_chain_roles=["核心零部件", "系统集成", "工业软件"],
        location_preference="广州",
        limit=5,
        data_mode="real",
    )
    profiles, source_summary, _limitations = await _profiles(request)
    cards = [
        score_enterprise(
            profile,
            industry=request.industry,
            target_chain_roles=request.target_chain_roles,
            data_mode="real",
        )
        for profile in profiles
    ]

    assert profiles
    assert source_summary["source"] == "local_json"
    assert source_summary["catalog_total"] >= len(profiles)
    assert all(card.data_mode == "real" for card in cards)
    assert all(card.evidence for card in cards)
    assert all(card.risk.level == "UNKNOWN" for card in cards)


@pytest.mark.asyncio
async def test_candidate_is_only_created_after_explicit_confirmation():
    profile = _profile()
    profile.enterprise_id = "DEMO-TARGET-001"
    profile.data_source = "demo_scenario"
    card = score_enterprise(
        profile,
        industry="机器人",
        target_chain_roles=["系统集成"],
        data_mode="demo",
    )
    scenario = InvestmentScenario(
        id="scenario-demo-001",
        name="演示机器人招商",
        industry="机器人",
        target_chain_roles=["系统集成"],
        result_limit=1,
        data_mode="demo",
        status="READY",
        recommendation_snapshot=[card.model_dump(mode="json")],
        snapshot_metadata={},
        created_by="demo-user",
    )

    class EmptyResult:
        @staticmethod
        def scalar_one_or_none():
            return None

    class FakeSession:
        def __init__(self):
            self.added = []

        async def get(self, model, key):
            if model is InvestmentScenario and key == scenario.id:
                return scenario
            return None

        async def execute(self, _statement):
            return EmptyResult()

        def add(self, value):
            self.added.append(value)

        async def flush(self):
            for value in self.added:
                if isinstance(value, InvestmentCandidate) and not value.id:
                    value.id = "candidate-demo-001"

        async def commit(self):
            return None

        async def refresh(self, _value):
            return None

    session = FakeSession()
    candidate, created = await create_candidate(
        session,
        CandidateCreate(
            scenario_id=scenario.id,
            recommendation=card,
            data_mode="demo",
        ),
        user_id="demo-user",
    )

    assert created is True
    assert candidate.enterprise_id == card.enterprise_id
    assert candidate.data_mode == "demo"
    assert candidate.status == "NEW"
    assert any(isinstance(value, CandidateAudit) for value in session.added)


@pytest.mark.asyncio
async def test_decision_graph_fans_out_risk_and_policy_per_enterprise(monkeypatch):
    import app.services.investment_decision_graph as decision_graph

    profiles = [_profile(), _profile()]
    profiles[0].enterprise_id = "ENT-ROBOT-001"
    profiles[0].name = "广州机器人企业一"
    profiles[1].enterprise_id = "ENT-ROBOT-002"
    profiles[1].name = "广州机器人企业二"
    risk_calls: list[str] = []
    policy_calls: list[str] = []

    def fake_industry(request, run_id):
        return AgentOutputEnvelope(
            agent="IndustryAgent",
            status="SUCCESS",
            result={"industry": request.industry},
            run_ref=f"{run_id}:IndustryAgent:scenario",
        )

    def fake_risk(profile, data_mode, run_id):
        risk_calls.append(profile.enterprise_id)
        evidence = EvidenceItem(
            id=f"{profile.enterprise_id}-risk-event",
            field="risk",
            claim="测试风险事件",
            value={"level": "MEDIUM"},
            source_type="test",
            source_title="测试风险来源",
            collected_at=datetime.now(timezone.utc),
            tool="test_risk_tool",
            snapshot_id=f"risk-{profile.enterprise_id}",
            confidence=0.9,
        )
        assessment = RiskAssessment(
            level="MEDIUM",
            score=60,
            reason=f"{profile.name}存在一条可核验风险事件",
            evidence_ids=[evidence.id],
        )
        return (
            AgentOutputEnvelope(
                agent="RiskAgent",
                enterprise_id=profile.enterprise_id,
                status="SUCCESS",
                result={"risk_level": "MEDIUM"},
                evidence_ids=[evidence.id],
                run_ref=f"{run_id}:RiskAgent:{profile.enterprise_id}",
            ),
            [evidence],
            assessment,
        )

    def fake_policy(profile, request, run_id, enterprise_evidence_ids):
        policy_calls.append(profile.enterprise_id)
        evidence = EvidenceItem(
            id=f"{profile.enterprise_id}-policy-match",
            field="policy_related",
            claim="测试政策相关",
            value={"title": "广州市机器人产业扶持政策"},
            source_type="test",
            source_title="测试政策来源",
            collected_at=datetime.now(timezone.utc),
            tool="test_policy_tool",
            snapshot_id=f"policy-{profile.enterprise_id}",
            confidence=0.8,
        )
        match = PolicyMatch(
            policy_id="POLICY-001",
            title="广州市机器人产业扶持政策",
            match_type="RELATED",
            reason="产业相关，资格待核验",
            evidence_ids=[evidence.id],
        )
        return (
            AgentOutputEnvelope(
                agent="PolicyAgent",
                enterprise_id=profile.enterprise_id,
                status="SUCCESS",
                result={"total_matched": 1},
                evidence_ids=[evidence.id],
                unknown_fields=["policy_eligibility"],
                run_ref=f"{run_id}:PolicyAgent:{profile.enterprise_id}",
            ),
            [evidence],
            [match],
        )

    monkeypatch.setattr(decision_graph, "_industry_agent_sync", fake_industry)
    monkeypatch.setattr(decision_graph, "_risk_agent_sync", fake_risk)
    monkeypatch.setattr(decision_graph, "_policy_agent_sync", fake_policy)

    request = InvestmentScenarioCreate(
        name="广州机器人产业园招商",
        industry="机器人",
        target_chain_roles=["核心零部件", "系统集成"],
        location_preference="广州",
        limit=2,
        data_mode="real",
    )
    result = await run_investment_decision(request, profiles)

    assert sorted(risk_calls) == ["ENT-ROBOT-001", "ENT-ROBOT-002"]
    assert sorted(policy_calls) == ["ENT-ROBOT-001", "ENT-ROBOT-002"]
    assert len(result.recommendations) == 2
    for card in result.recommendations:
        assert set(card.agent_outputs) == {
            "Supervisor",
            "IndustryAgent",
            "InvestmentAgent",
            "EnterpriseData",
            "RiskAgent",
            "PolicyAgent",
        }
        assert card.risk.level == "MEDIUM"
        assert card.policy_matches[0].match_type == "RELATED"
        assert "policy_fit" in card.unknown_fields
        assert "risk" not in card.unknown_fields
        assert len(card.trace_refs) == 6
        signals = card.agent_outputs["EnterpriseData"].result["signals"]
        assert any(item["field"] == "recruitment_trend" for item in signals)
