from datetime import datetime, timezone
import pytest

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


def test_enterprise_wide_table_creates_one_record_per_company():
    text = """
| 企业名称 | 统一社会信用代码 | 注册资本 | 注册地址 | 经营状态 | 经营范围 | 专利数量 |
|---|---|---|---|---|---|---|
| 广州甲机器人有限公司 | 91440101TEST000001 | 1200万元 | 广州市天河区 | 存续 | 机器人研发 | 8 |
| 广州乙智能装备有限公司 | 91440101TEST000002 | 800万元 | 广州市黄埔区 | 在营 | 智能装备制造 | 5 |
"""
    result = extract_document_structure(
        text,
        category="企业资料",
        source_title="企业台账.csv",
        document_id="doc-wide",
    )

    assert result["enterprise_count"] == 2
    assert [item["name"] for item in result["enterprises"]] == [
        "广州甲机器人有限公司",
        "广州乙智能装备有限公司",
    ]
    assert result["enterprises"][0]["patent_count"] == 8


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


def test_industry_condition_uses_business_scope_evidence():
    from app.services.policy_eligibility_service import evaluate_policy_conditions

    profile = EnterpriseProfile(
        enterprise_id="ENT-ROBOT-1",
        name="广州测试科技有限公司",
        industry="robotics",
        business_scope="具身智能机器人核心零部件与控制系统研发",
        data_source="park_document",
        evidence=[{"type": "park_private_document", "value": "企业资料", "document_id": "doc-1"}],
    )
    status, results, _reason = evaluate_policy_conditions(
        profile,
        [{
            "condition_code": "SOURCE_INDUSTRY",
            "label": "政策适用产业范围",
            "field": "industry",
            "operator": "CONTAINS",
            "expected_value": ["具身智能机器人", "核心零部件"],
            "mandatory": True,
            "review_status": "REVIEWED",
            "source_text": "本政策措施所称企业是指从事具身智能机器人核心零部件生产的相关企业。",
        }],
        enterprise_evidence_ids=["enterprise-doc-1"],
        policy_evidence_id="policy-1",
    )

    assert status == "ELIGIBLE"
    assert results[0].status == "SATISFIED"


@pytest.mark.asyncio
async def test_reimporting_archived_document_restores_without_duplicate(tmp_path, monkeypatch):
    import app.services.park_document_service as library

    root = tmp_path / "library"
    monkeypatch.setattr(library, "LIBRARY_ROOT", root)
    monkeypatch.setattr(library, "INDEX_PATH", root / "index.json")
    monkeypatch.setattr(library, "FILES_DIR", root / "files")
    monkeypatch.setattr(library, "TEXT_DIR", root / "text")
    monkeypatch.setattr(library, "STRUCTURED_DIR", root / "structured")
    content = "# 园区规划\n\n这是同一份可检索的园区规划正文。"
    first_source = tmp_path / "first.md"
    first_source.write_text(content, encoding="utf-8")
    first = await library.import_park_document(
        first_source,
        original_name="规划.md",
        category="园区规划",
        tags=[],
        created_by="admin",
    )
    assert library.delete_park_document(first["id"], archived_by="admin") is True

    second_source = tmp_path / "second.md"
    second_source.write_text(content, encoding="utf-8")
    second = await library.import_park_document(
        second_source,
        original_name="规划.md",
        category="园区规划",
        tags=[],
        created_by="admin",
    )

    assert second["id"] == first["id"]
    assert second["restored"] is True
    assert len(library.list_park_documents()) == 1
