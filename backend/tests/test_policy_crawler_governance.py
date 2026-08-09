from pathlib import Path

from app.core.policy_crawler_access import ROOT_ADMIN_USER_ID, is_root_admin
from app.core.security import UserContext
from app.services.policy_crawler_engine import canonical_url, deduplicate_entries


def _entry(tmp_path: Path, name: str, url: str, content: str, source_key: str) -> dict:
    path = tmp_path / name
    path.write_text(f"# 来源: {url}\n\n{content}", encoding="utf-8")
    return {
        "url": url,
        "file": name,
        "size": path.stat().st_size,
        "source_key": source_key,
        "included": True,
    }


def test_only_bootstrap_super_admin_is_crawler_owner():
    assert is_root_admin(
        UserContext(user_id=ROOT_ADMIN_USER_ID, username="admin", role="super_admin")
    )
    assert not is_root_admin(
        UserContext(user_id="later-admin", username="later", role="super_admin")
    )
    assert not is_root_admin(
        UserContext(user_id=ROOT_ADMIN_USER_ID, username="admin", role="park_manager")
    )


def test_canonical_url_removes_mobile_form_query_and_fragment():
    assert canonical_url(
        "https://www.gz.gov.cn/example/content/mpost_123.html?a=1#x"
    ) == "https://www.gz.gov.cn/example/content/post_123.html"


def test_same_document_number_is_cross_source_duplicate(tmp_path: Path):
    entries = [
        _entry(
            tmp_path,
            "issuer.md",
            "https://gxj.gz.gov.cn/a/content/post_1.html",
            "# 广州市机器人产业扶持办法\n\n文号：穗工信规字〔2026〕1号\n\n" + "政策正文" * 100,
            "gz_gxj",
        ),
        _entry(
            tmp_path,
            "repost.md",
            "https://sw.gz.gov.cn/b/content/post_2.html",
            "# 广州市机器人产业扶持办法\n\n文号：穗工信规字[2026]1号\n\n" + "转载正文" * 100,
            "gz_swj",
        ),
    ]

    result, stats = deduplicate_entries(entries, tmp_path)

    assert stats["duplicates"] == 1
    assert stats["included"] == 1
    assert sum(1 for item in result if item["included"] is False) == 1
    assert next(item for item in result if not item["included"])["duplicate_of"]


def test_same_title_different_document_numbers_are_versions(tmp_path: Path):
    entries = [
        _entry(
            tmp_path,
            "old.md",
            "https://www.gz.gov.cn/a/content/post_10.html",
            "# 关于延长产业扶持政策有效期的通知\n\n文号：穗发改规字〔2025〕1号\n\n发布日期：2025-01-01\n\n" + "旧版" * 100,
            "gz_fgw",
        ),
        _entry(
            tmp_path,
            "new.md",
            "https://www.gz.gov.cn/a/content/post_11.html",
            "# 关于延长产业扶持政策有效期的通知\n\n文号：穗发改规字〔2026〕2号\n\n发布日期：2026-01-01\n\n" + "新版" * 100,
            "gz_fgw",
        ),
    ]

    result, stats = deduplicate_entries(entries, tmp_path)

    assert stats["duplicates"] == 0
    assert stats["version_relations"] == 1
    assert all(item["included"] for item in result)
    assert any(item.get("related_version_of") for item in result)
