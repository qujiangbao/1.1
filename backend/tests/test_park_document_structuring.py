from datetime import datetime, timezone

from app.schemas.enterprise import EnterpriseProfile
from app.services.investment_scoring_service import score_enterprise
from app.services.park_document_service import _is_policy_material
from app.services.park_document_structuring import extract_document_structure


def test_enterprise_report_is_structured_without_treating_clearance_as_risk():
    text = """
## 1. 广州测试机器人股份有限公司

| 项目 | 内容 |
|---|---|
| 统一社会信用代码 | 91440101TEST000001 |
| 注册资本 | 2亿元人民币 |
| 注册地址 | 广州市天河区测试路1号 |
| 经营状态 | 存续 |

### 1.2 经营范围

机器人本体、伺服驱动器及控制系统研发。

| 审核维度 | 状态 | 详情 | 来源 |
|---|---|---|---|
| 行政处罚 | 无记录 | 未发现行政处罚记录 | 信用广州 |
| 监管措施 | 1起 | 2025年收到监管警示函，已整改 | 监管机关 |
"""
    result = extract_document_structure(
        text,
        category="企业资料",
        source_title="测试企业报告.md",
        document_id="doc-1",
    )
    assert result["enterprise_count"] == 1
    record = result["enterprises"][0]
    assert record["credit_code"] == "91440101TEST000001"
    assert record["capital_amount"] == 20000
    assert record["industry"] == "robotics"
    assert [item["title"] for item in record["_risk_events"]] == ["监管措施"]


def test_policy_search_excludes_enterprise_category_even_with_policy_words():
    assert not _is_policy_material({
        "name": "机器人政策适配企业审核报告.md",
        "category": "企业资料",
        "tags": ["政策", "机器人"],
    })
    assert _is_policy_material({
        "name": "天河区机器人政策.md",
        "category": "园区综合资料",
        "tags": ["机器人"],
    })


def test_recommendation_score_is_hidden_below_evidence_gate():
    profile = EnterpriseProfile(
        enterprise_id="ENT-1",
        name="广州测试机器人有限公司",
        credit_code="91440101TEST000001",
        industry="机器人",
        business_scope="机器人本体和控制系统研发",
        location="广州",
        enterprise_status="存续",
        confidence_score=0.9,
        source_time=datetime.now(timezone.utc),
        evidence=[{"type": "source", "value": "企业公开资料", "url": "https://example.test"}],
    )
    card = score_enterprise(
        profile,
        industry="机器人",
        target_chain_roles=["核心零部件", "系统集成"],
        data_mode="real",
    )
    assert card.score_breakdown["industry_fit"].score is not None
    assert card.score_breakdown["technology"].score is not None
    assert card.score_breakdown["data_completeness"].score is not None
    assert card.overall_score is None
    assert card.data_status == "DATA_INSUFFICIENT"
    assert "暂不形成推荐结论" in card.recommendation
