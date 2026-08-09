"""Enrich enterprise profiles with inferred fields from existing meta data.

Reads enterprise_import_clean.json and adds:
  - funding_stage: parsed from source title / business_scope / tags
  - expansion_willingness: inferred from city + keywords in source title / business_scope
  - growth_rate: estimated from capital_amount + keywords if available

Writes enterprise_import_enriched.json so the LocalJsonAdapter picks it up.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = BACKEND_ROOT / "data" / "enterprises" / "enterprise_import_clean.json"
OUTPUT_PATH = BACKEND_ROOT / "data" / "enterprises" / "enterprise_import_enriched.json"

# ── keyword lists ──────────────────────────────────────────────
FUNDING_KEYWORDS: list[tuple[str, str]] = [
    (r"IPO|上市|科创板|创业板|北交所|纳斯达克|纽交所", "IPO/已上市"),
    (r"E轮|Pre-IPO|战略投资(?!.*天使)", "E轮及以上"),
    (r"D轮|D\+轮", "D轮"),
    (r"C轮|C\+轮|C\+\+轮", "C轮"),
    (r"B轮|B\+轮|B\+\+轮", "B轮"),
    (r"A轮|A\+轮|Pre-A", "A轮"),
    (r"天使轮|种子轮|天使\+轮", "天使轮/种子轮"),
    (r"融资(?!.*轮)|完成.*融资|获得.*投资|完成.*交割|pre-A", "已融资"),
]

EXPANSION_KEYWORDS = [
    "扩产", "新增产线", "二期工程", "三期工程", "新厂房", "落成",
    "成立", "注册", "新设", "子.*公司", "分公司", "办事处",
    "入驻", "落地", "签约.*园区", "产业园",
    "招聘.*广州", "广州.*招聘", "南沙.*公司",
]

TECH_SIGNALS = [
    "高新技术企业", "专精特新", "小巨人", "瞪羚企业", "独角兽",
    "发明专利", "实用新型", "软件著作权", "集成电路布图",
    "科技型中小企业", "创新型企业",
]

GUANGZHOU_DISTRICTS = [
    "南沙", "天河", "黄埔", "越秀", "荔湾", "海珠", "白云",
    "番禺", "花都", "增城", "从化", "广州",
]


def _combine_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    meta = record.get("_meta") or {}
    for key in ("source_title", "source_url"):
        val = meta.get(key)
        if isinstance(val, str):
            parts.append(val)
    for key in ("business_scope", "industry", "name", "legal_representative"):
        val = record.get(key)
        if isinstance(val, str):
            parts.append(val)
    for tag_list in (record.get("tags") or []):
        if isinstance(tag_list, list):
            parts.extend(str(t) for t in tag_list)
    return " ".join(parts)


def infer_funding_stage(text: str) -> str | None:
    for pattern, stage in FUNDING_KEYWORDS:
        if re.search(pattern, text, re.IGNORECASE):
            return stage
    return None


def infer_expansion(city: str | None, text: str) -> str | None:
    """Return a willingness label or None if uncertain."""
    score = 0
    if city and any(d in str(city) for d in GUANGZHOU_DISTRICTS):
        score += 1  # already in Guangzhou = stronger signal
    for kw in EXPANSION_KEYWORDS:
        if re.search(kw, text, re.IGNORECASE):
            score += 1
    if score >= 2:
        return "有明确扩产或落地广州信号"
    if score == 1:
        return "存在潜在扩产意愿（信号较弱）"
    return None


def infer_growth_rate(capital: float | None, text: str) -> float | None:
    """Rough estimate based on capital scale & tech signals."""
    has_tech = any(re.search(s, text, re.IGNORECASE) for s in TECH_SIGNALS)
    if capital is not None and capital > 0:
        if capital >= 50000:
            return 22.0
        if capital >= 10000:
            return 18.0 if has_tech else 14.0
        if capital >= 1000:
            return 12.0
        return 8.0
    if has_tech:
        return 10.0
    return None


def enrich() -> None:
    records: list[dict[str, Any]] = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    stats = {
        "total": len(records),
        "funding_stage_added": 0,
        "expansion_added": 0,
        "growth_rate_added": 0,
    }

    for rec in records:
        text = _combine_text(rec)
        changed = False

        if (rec.get("funding_stage") or rec.get("funding_stage") == "") is not True:
            stage = infer_funding_stage(text)
            if stage:
                rec["funding_stage"] = stage
                stats["funding_stage_added"] += 1
                changed = True

        if (rec.get("expansion_willingness") or rec.get("expansion_willingness") == "") is not True:
            willingness = infer_expansion(rec.get("city"), text)
            if willingness:
                rec["expansion_willingness"] = willingness
                stats["expansion_added"] += 1
                changed = True

        if (rec.get("growth_rate") or rec.get("growth_rate") == "") is not True:
            rate = infer_growth_rate(rec.get("capital_amount"), text)
            if rate is not None:
                rec["growth_rate"] = rate
                stats["growth_rate_added"] += 1
                changed = True

    OUTPUT_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Enriched {stats['total']} records:")
    print(f"  funding_stage:       {stats['funding_stage_added']} added")
    print(f"  expansion_willingness: {stats['expansion_added']} added")
    print(f"  growth_rate:         {stats['growth_rate_added']} added")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    enrich()
