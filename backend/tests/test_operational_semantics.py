import pytest
from types import SimpleNamespace

from app.agents.registry import AGENT_REGISTRY
from app.agents.executor import _summary
from app.langgraph.nodes.policy_nodes import policy_matcher_node
from app.langgraph.nodes.service_nodes import get_service_graph
from app.langgraph.nodes.supervisor_nodes import _keyword_intent_fallback
from app.api.v1.policy_management import (
    _candidate_eligibility_item,
    _enterprise_eligibility_item,
)
from app.services.policy_applicability_service import classify_policy_applicability
from app.schemas.enterprise import EnterpriseProfile
from app.services.park_document_service import _query_terms


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("分析机器人产业链上游缺口", "industry_analysis"),
        ("寻找谐波减速器招商目标企业", "investment_search"),
        ("核验候选企业客户集中度风险", "risk_single"),
        ("匹配中试补贴申报条件", "policy_match"),
        ("汇总经营指标和招商漏斗", "dashboard_kpi"),
        ("办公室空调故障需要报修", "service_request"),
    ],
)
def test_keyword_fallback_covers_each_operational_agent(query, expected_intent):
    result = _keyword_intent_fallback(query)
    assert expected_intent in result["intents"]


def test_generic_enterprise_word_does_not_force_investment_agent():
    result = _keyword_intent_fallback("园区企业办公室空调故障，请安排报修")
    assert result["intents"] == ["service_request"]


def test_unrecognized_query_does_not_default_to_investment():
    result = _keyword_intent_fallback("你好")
    assert result["intent"] == "general_query"
    assert result["intents"] == []


def test_natural_chinese_document_query_is_segmented_for_recall():
    terms = _query_terms("启航智造产业园有哪些招商目标")
    assert "启航" in terms
    assert "智造" in terms
    assert "招商" in terms
    assert "目标" in terms
    assert "哪些" not in terms


def test_document_query_prefix_does_not_dilute_private_document_score():
    terms = _query_terms("园区资料库查询 启航智造 HORIZON-2026 中试政策")
    assert "园区资料库查询" not in terms
    assert "查询" not in terms
    assert "horizon-2026" in terms


def test_enterprise_service_is_advice_only_without_fake_ticket():
    result = get_service_graph().invoke({
        "task_id": "service-test-001",
        "input": {"request": "办公室空调故障，请安排报修"},
        "status": "idle",
        "tools_used": [],
    })
    response = result["final_response"]
    assert response["service_category"] == "space_service"
    assert response["ticket_created"] is False
    assert response["ticket_id"] is None
    assert "正式企业服务工单系统" in response["notice"]


def test_enterprise_service_capabilities_do_not_claim_ticket_management():
    capabilities = AGENT_REGISTRY["EnterpriseServiceAgent"]["capabilities"]
    assert "ticket_management" not in capabilities
    assert "manual_handoff_advice" in capabilities


def test_policy_summary_is_compact_and_does_not_claim_exhaustive_matching():
    policies = [
        {
            "policy_id": f"policy-{index}",
            "title": f"候选政策 {index}",
            "match_score": 80 - index,
            "matched_terms": ["机器人"],
        }
        for index in range(1, 6)
    ]
    summary = _summary("PolicyAgent", {
        "total_matched": 5,
        "returned_count": 5,
        "policies": policies,
    })

    assert "工作台展示相关度最高的前 3 条" in summary
    assert "不是完整政策清单" in summary
    assert "候选政策 3" in summary
    assert "候选政策 4" not in summary


def test_policy_matcher_exposes_score_and_matched_terms():
    state = {
        "query": "机器人 系统集成 广州",
        "filtered_chunks": [{
            "policy_id": "policy-robot-1",
            "title": "机器人系统集成扶持办法",
            "content": "支持机器人系统集成企业在广州落地。",
            "score": 0.82,
            "metadata": {"title": "机器人系统集成扶持办法"},
            "evidence": [],
        }],
    }

    result = policy_matcher_node(state)
    match = result["matched_policies"][0]
    assert match["match_score"] == 82
    assert match["matched_terms"] == ["机器人", "系统集成"]


def test_policy_candidate_result_explains_who_and_how():
    candidate = SimpleNamespace(
        id="candidate-1",
        enterprise_id="ENT-1",
        enterprise_name="测试机器人企业",
        status="CONTACTING",
        evidence=[{"id": "enterprise-evidence-1"}],
        updated_at=None,
    )
    profile = EnterpriseProfile(
        enterprise_id="ENT-1",
        name="测试机器人企业",
        industry="机器人",
        location="广州",
        enterprise_status="存续",
        data_source="test",
        evidence=[{"type": "snapshot", "value": "test"}],
    )
    item = _candidate_eligibility_item(
        candidate,
        profile,
        "policy-1",
        [{
            "condition_code": "REGISTERED_REGION",
            "label": "注册地要求",
            "field": "region",
            "operator": "CONTAINS",
            "expected_value": ["广州"],
            "mandatory": True,
            "review_status": "REVIEWED",
            "source_text": "企业注册地须在广州",
        }],
        {"match_score": 82, "matched_terms": ["机器人"]},
    )

    assert item["enterprise_name"] == "测试机器人企业"
    assert item["match_type"] == "ELIGIBLE"
    assert item["condition_results"][0]["status"] == "SATISFIED"
    assert item["condition_results"][0]["actual_value"] == "广州"


def test_draft_policy_condition_shows_actual_value_without_claiming_eligibility():
    candidate = SimpleNamespace(
        id="candidate-2",
        enterprise_id="ENT-2",
        enterprise_name="待核验企业",
        status="NEW",
        evidence=[{"id": "enterprise-evidence-2"}],
        updated_at=None,
    )
    profile = EnterpriseProfile(
        enterprise_id="ENT-2",
        name="待核验企业",
        industry="机器人",
        location="广州黄埔",
        enterprise_status="存续",
        data_source="test",
    )
    item = _candidate_eligibility_item(
        candidate,
        profile,
        "policy-2",
        [{
            "condition_code": "REGISTERED_REGION",
            "label": "注册地要求",
            "field": "region",
            "operator": "CONTAINS",
            "expected_value": ["广州"],
            "mandatory": True,
            "review_status": "DRAFT",
            "source_text": "系统模板建议（非政策原文）",
        }],
        {"match_score": 70, "matched_terms": ["机器人"]},
    )

    assert item["match_type"] == "UNKNOWN"
    assert item["condition_results"][0]["status"] == "NEEDS_MANUAL_REVIEW"
    assert item["condition_results"][0]["actual_value"] == "广州黄埔"


def test_full_catalog_preview_uses_imported_enterprise_evidence():
    profile = EnterpriseProfile(
        enterprise_id="ENT-IMPORTED-1",
        name="园区导入机器人企业",
        industry="机器人",
        location="广州天河",
        enterprise_status="存续",
        data_source="local_json",
        evidence=[{
            "type": "source",
            "value": "园区导入企业资料.docx",
            "document_id": "doc-1",
        }],
    )
    item = _enterprise_eligibility_item(
        profile,
        "policy-robot-1",
        [{
            "condition_code": "REGISTERED_REGION",
            "label": "注册地要求",
            "field": "region",
            "operator": "CONTAINS",
            "expected_value": ["广州"],
            "mandatory": True,
            "review_status": "DRAFT",
            "source_text": "企业注册地应在广州",
        }],
    )

    assert item["candidate_id"] is None
    assert item["enterprise_name"] == "园区导入机器人企业"
    assert item["match_type"] == "POTENTIALLY_ELIGIBLE"
    assert item["decision_basis"] == "PRELIMINARY"
    assert item["preliminary_outcome"] == "MATCH"
    assert item["condition_results"][0]["preview_status"] == "SATISFIED"
    assert item["evidence_count"] == 1


@pytest.mark.parametrize(
    ("title", "expected_mode"),
    [
        ("广州市机器人产业扶持资金申报通知", "ELIGIBILITY"),
        ("关于征求机器人产业政策意见的公告", "REFERENCE_ONLY"),
        ("机器人项目拟入选名单公示", "REFERENCE_ONLY"),
        ("广州市机器人产业发展情况通报", "UNCLASSIFIED"),
    ],
)
def test_policy_applicability_hides_non_application_documents(title, expected_mode):
    mode, _reason = classify_policy_applicability(SimpleNamespace(
        title=title,
        status="active",
    ))
    assert mode == expected_mode


def test_policy_applicability_uses_application_signals_from_body():
    mode, _reason = classify_policy_applicability(SimpleNamespace(
        title="广州市机器人产业发展工作方案",
        content="三、支持对象和申报条件。申报单位应当依法登记并提交申请材料。",
        status="active",
    ))
    assert mode == "ELIGIBILITY"
