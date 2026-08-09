import asyncio
import json

from app.tools.adapters.local_json import LocalJsonAdapter


def _write_enterprises(path):
    payload = [
        {
            "name": "广州甲机器人有限公司",
            "credit_code": "91440101TEST000001",
            "city": "广州市天河区",
            "industry": "机器人",
            "business_scope": "工业机器人研发",
            "capital_amount": 1200,
            "capital_currency": "万元人民币",
            "patent_count": None,
            "tags": ["人工智能", "智能制造"],
            "_meta": {"source_title": "公开企业名录"},
        },
        {
            "name": "广州乙智能科技有限公司",
            "credit_code": None,
            "city": "广州市南沙区",
            "industry": "人工智能",
            "capital_amount": 300,
            "capital_currency": "万元人民币",
            "patent_count": None,
        },
        {
            "name": " 广州乙智能科技有限公司 ",
            "credit_code": "",
            "business_scope": "软件开发",
        },
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_local_json_preserves_unknown_patents_and_deduplicates_by_name(tmp_path):
    data_path = tmp_path / "enterprises.json"
    _write_enterprises(data_path)
    adapter = LocalJsonAdapter(data_path)

    stats = adapter.stats()
    result = asyncio.run(adapter.search_enterprises_advanced("", limit=10))

    assert stats["raw_records"] == 3
    assert stats["total_enterprises"] == 2
    assert stats["deduplicated_records"] == 1
    assert stats["coverage"]["patent_count"]["rate"] == 0
    assert result.total == 2
    assert all(item.patents_count is None for item in result.enterprises)
    fallback = next(item for item in result.enterprises if item.credit_code is None)
    assert fallback.enterprise_id.startswith("ENT-NAME-")
    assert fallback.data_quality["identity_key"] == "name"


def test_local_json_filters_and_sorts_by_numeric_capital(tmp_path):
    data_path = tmp_path / "enterprises.json"
    _write_enterprises(data_path)
    adapter = LocalJsonAdapter(data_path)

    result = asyncio.run(
        adapter.search_enterprises_advanced(
            "",
            min_capital=200,
            sort_by="capital_desc",
            limit=10,
        )
    )

    assert [item.capital_amount for item in result.enterprises] == [1200.0, 300.0]
    assert result.enterprises[0].registered_capital == "1,200 万元人民币"


def test_local_json_search_reports_actual_matching_fields(tmp_path):
    data_path = tmp_path / "enterprises.json"
    _write_enterprises(data_path)
    adapter = LocalJsonAdapter(data_path)

    result = asyncio.run(adapter.search_enterprises("机器人", limit=10))

    assert result.total == 1
    assert result.enterprises[0].name == "广州甲机器人有限公司"
    assert "企业名称" in result.enterprises[0].match_reason
    assert "行业" in result.enterprises[0].match_reason


def test_local_json_merges_name_fallback_into_unique_credit_identity(tmp_path):
    data_path = tmp_path / "enterprises.json"
    data_path.write_text(
        json.dumps([
            {
                "name": "广州同名企业有限公司",
                "credit_code": "91440101TEST000099",
                "industry": "人工智能",
            },
            {
                "name": " 广州同名企业有限公司 ",
                "credit_code": None,
                "business_scope": "软件开发",
            },
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    adapter = LocalJsonAdapter(data_path)

    result = asyncio.run(adapter.search_enterprises("", limit=10))

    assert result.total == 1
    assert result.enterprises[0].enterprise_id == "ENT-CC-91440101TEST000099"
    assert result.enterprises[0].business_scope == "软件开发"
