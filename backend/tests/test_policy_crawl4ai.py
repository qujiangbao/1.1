import json

import pytest

from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData


def _write_policy_cache(tmp_path):
    policy = tmp_path / "policy_123.md"
    policy.write_text(
        """# 来源: https://www.gz.gov.cn/example/content/post_123.html

基本信息
* 文 号： 穗发改规字〔2026〕1号
* 实施日期： 2026-01-01
* 失效日期： 2099-12-31
* 发布机关： 广州市发展和改革委员会
* 文件状态： 有效

# 广州市机器人产业扶持办法

对机器人、智能装备和专精特新中小企业提供研发补贴。
""",
        encoding="utf-8",
    )
    (tmp_path / "_index.json").write_text(
        json.dumps([{
            "url": "https://www.gz.gov.cn/example/content/post_123.html",
            "file": policy.name,
            "size": policy.stat().st_size,
        }], ensure_ascii=False),
        encoding="utf-8",
    )


def test_crawl4ai_policy_search_returns_traceable_metadata(tmp_path):
    _write_policy_cache(tmp_path)
    adapter = PolicyCrawl4AIData(tmp_path)

    results = adapter.search("机器人研发补贴", top_k=3)

    assert len(results) == 1
    result = results[0]
    assert result["policy_id"] == "GZ-FG-123"
    assert result["metadata"]["title"] == "广州市机器人产业扶持办法"
    assert result["metadata"]["document_number"] == "穗发改规字〔2026〕1号"
    assert result["metadata"]["department"] == "广州市发展和改革委员会"
    assert result["metadata"]["source_url"].startswith("https://www.gz.gov.cn/")
    assert result["evidence"][0]["type"] == "government_policy"


def test_crawl4ai_policy_search_honors_region_filter(tmp_path):
    _write_policy_cache(tmp_path)
    adapter = PolicyCrawl4AIData(tmp_path)

    assert adapter.search("机器人", filters={"region": "深圳市"}) == []
    assert len(adapter.search("机器人", filters={"region": "广州市"})) == 1


def test_crawl4ai_policy_cache_rejects_path_traversal(tmp_path):
    (tmp_path / "_index.json").write_text(
        json.dumps([{
            "url": "https://www.gz.gov.cn/example/content/post_123.html",
            "file": "../outside.md",
            "size": 10,
        }]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no valid documents"):
        PolicyCrawl4AIData(tmp_path).stats()


def test_crawl4ai_policy_cache_requires_government_source(tmp_path):
    policy = tmp_path / "policy_123.md"
    policy.write_text("# 非政府来源\n内容", encoding="utf-8")
    (tmp_path / "_index.json").write_text(
        json.dumps([{
            "url": "https://example.com/policy",
            "file": policy.name,
            "size": policy.stat().st_size,
        }]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no valid documents"):
        PolicyCrawl4AIData(tmp_path).stats()


def test_crawl4ai_policy_preserves_district_metadata(tmp_path):
    policy = tmp_path / "policy_hp_department_456.md"
    policy.write_text(
        """# 来源: https://www.gz.gov.cn/gfxwj/qjgfxwj/hpq/qbm/content/post_456.html

# 广州开发区产业园项目落户扶持办法

发布机关：广州市黄埔区工业和信息化局

支持先进制造项目向黄埔区产业园集聚。
""",
        encoding="utf-8",
    )
    (tmp_path / "_index.json").write_text(
        json.dumps([{
            "url": (
                "https://www.gz.gov.cn/gfxwj/qjgfxwj/"
                "hpq/qbm/content/post_456.html"
            ),
            "file": policy.name,
            "size": policy.stat().st_size,
            "source_key": "hp_department",
            "source_name": "黄埔区广州开发区区部门规范性文件",
            "level": "district",
            "region": "广州市黄埔区",
        }], ensure_ascii=False),
        encoding="utf-8",
    )

    result = PolicyCrawl4AIData(tmp_path).search(
        "产业园项目落户",
        filters={"level": "district", "region": "黄埔区"},
    )[0]

    assert result["policy_id"] == "GZ-HP-DEPT-456"
    assert result["metadata"]["level"] == "district"
    assert result["metadata"]["region"] == "广州市黄埔区"
    assert result["metadata"]["region_scope"] == ["广州市", "广州市黄埔区"]


def test_crawl4ai_policy_excludes_non_relevant_audit_entry(tmp_path):
    policy = tmp_path / "policy_hp_department_789.md"
    policy.write_text(
        """# 来源: https://www.gz.gov.cn/example/content/post_789.html

# 黄埔区学前教育资助实施方案

非产业园政策。
""",
        encoding="utf-8",
    )
    (tmp_path / "_index.json").write_text(
        json.dumps([{
            "url": "https://www.gz.gov.cn/example/content/post_789.html",
            "file": policy.name,
            "size": policy.stat().st_size,
            "relevant": False,
        }], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no valid documents"):
        PolicyCrawl4AIData(tmp_path).stats()


def test_crawl4ai_policy_loads_latest_clean_snapshot_and_dynamic_metadata(tmp_path):
    older = tmp_path / "snapshot-20260725-100000"
    latest = tmp_path / "snapshot-20260726-100000"
    for snapshot in (older, latest):
        (snapshot / "clean").mkdir(parents=True)
        clean_file = snapshot / "clean" / "policy.md"
        clean_file.write_text("# 人工智能项目申报通知\n支持企业申报专项资金。", encoding="utf-8")
        (snapshot / "_clean_manifest.json").write_text(
            json.dumps([{
                "url": "https://www.gz.gov.cn/example/content/post_999.html",
                "included": True,
                "clean_file": "clean/policy.md",
                "title": "人工智能项目申报通知",
                "department": "广州市科学技术局",
                "publish_date": "2026-07-26",
                "document_number": "穗科字〔2026〕9号",
                "document_type": "project_application",
                "deadline_dates": ["2026-08-31"],
                "funding_available": True,
                "region": "广州市天河区",
                "level": "district",
                "source_key": "gz_kjj",
            }], ensure_ascii=False),
            encoding="utf-8",
        )
        (snapshot / "_clean_report.json").write_text(
            json.dumps({
                "raw_records": 2,
                "included_records": 1,
                "failed_records": 0,
                "with_deadline": 1,
                "with_funding": 1,
            }),
            encoding="utf-8",
        )

    adapter = PolicyCrawl4AIData(tmp_path)
    result = adapter.search("人工智能 项目申报 专项资金", top_k=1)[0]
    stats = adapter.stats()

    assert adapter.data_dir == latest
    assert result["metadata"]["document_type"] == "project_application"
    assert result["metadata"]["deadlines"] == ["2026-08-31"]
    assert result["metadata"]["funding_available"] is True
    assert stats["with_deadline"] == 1
    assert stats["failed_records"] == 0
