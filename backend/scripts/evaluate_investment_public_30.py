"""Generate the formal deterministic report for the public 30-company set."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.investment_scoring_service import score_enterprise
from app.tools.adapters.local_json import LocalJsonAdapter


DATASET_PATH = BACKEND_ROOT / "evaluation" / "investment_public_30.json"
REPORT_JSON = BACKEND_ROOT / "reports" / "investment_public_30_latest.json"
REPORT_MD = BACKEND_ROOT / "reports" / "investment_public_30_latest.md"


def _rate(passed: int, total: int) -> float:
    return round(passed / total * 100, 2) if total else 0.0


def evaluate() -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    adapter = LocalJsonAdapter(BACKEND_ROOT / dataset["snapshot"])
    records = {record.get("name"): record for record in adapter._load()}
    rows = []

    for item in dataset["enterprises"]:
        record = records.get(item["name"])
        if record is None:
            rows.append({"name": item["name"], "found": False})
            continue
        profile = adapter._to_profile(record)
        first = score_enterprise(
            profile,
            industry="人工智能",
            target_chain_roles=["人工智能", "工业软件", "系统集成"],
            data_mode="real",
        )
        second = score_enterprise(
            profile,
            industry="人工智能",
            target_chain_roles=["人工智能", "工业软件", "系统集成"],
            data_mode="real",
        )
        evidence_ids = {evidence.id for evidence in first.evidence}
        linked = all(
            dimension.score is None
            or (
                bool(dimension.evidence_ids)
                and set(dimension.evidence_ids).issubset(evidence_ids)
            )
            for dimension in first.score_breakdown.values()
        )
        source_urls = {
            evidence.source_url
            for evidence in first.evidence
            if evidence.source_url
        }
        missing_not_zero = all(
            first.score_breakdown[field].score is None
            for field in ("growth", "landing_intent", "policy_fit")
        )
        rows.append(
            {
                "name": item["name"],
                "enterprise_id": profile.enterprise_id,
                "found": True,
                "source_traceable": item["source_url"] in source_urls,
                "evidence_linked": linked,
                "missing_not_zero": missing_not_zero,
                "risk_is_unknown_without_records": first.risk.level == "UNKNOWN",
                "deterministic": (
                    first.model_dump(mode="json")
                    == second.model_dump(mode="json")
                ),
                "overall_score": first.overall_score,
                "confidence": first.confidence,
                "unknown_fields": first.unknown_fields,
            }
        )

    found = [row for row in rows if row.get("found")]
    checks = {
        "dataset_size": len(rows),
        "found_count": len(found),
        "source_traceability_rate": _rate(
            sum(bool(row["source_traceable"]) for row in found),
            len(rows),
        ),
        "evidence_linkage_rate": _rate(
            sum(bool(row["evidence_linked"]) for row in found),
            len(rows),
        ),
        "missing_value_integrity_rate": _rate(
            sum(bool(row["missing_not_zero"]) for row in found),
            len(rows),
        ),
        "risk_unknown_integrity_rate": _rate(
            sum(bool(row["risk_is_unknown_without_records"]) for row in found),
            len(rows),
        ),
        "deterministic_repeat_rate": _rate(
            sum(bool(row["deterministic"]) for row in found),
            len(rows),
        ),
    }
    thresholds = {
        "found_count": 30,
        "source_traceability_rate": 100.0,
        "evidence_linkage_rate": 100.0,
        "missing_value_integrity_rate": 100.0,
        "risk_unknown_integrity_rate": 100.0,
        "deterministic_repeat_rate": 100.0,
    }
    passed = all(checks[key] >= value for key, value in thresholds.items())
    return {
        "report_id": "investment-public-30-latest",
        "dataset_id": dataset["dataset_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scoring_version": "investment-score-v1.0",
        "scope": (
            "验证数据可追溯、缺失值不按0分、风险未知边界、证据引用和"
            "确定性重复；不把公开快照当作招商成败金标。"
        ),
        "passed": passed,
        "thresholds": thresholds,
        "metrics": checks,
        "cases": rows,
    }


def _markdown(report: dict) -> str:
    status = "通过" if report["passed"] else "未通过"
    metrics = report["metrics"]
    lines = [
        "# 30家公开企业招商评分自动评测报告",
        "",
        f"- 结果：**{status}**",
        f"- 数据集：`{report['dataset_id']}`",
        f"- 评分版本：`{report['scoring_version']}`",
        f"- 生成时间：{report['generated_at']}",
        f"- 评测边界：{report['scope']}",
        "",
        "## 汇总指标",
        "",
        "| 指标 | 结果 | 阈值 |",
        "|---|---:|---:|",
        f"| 样本数 | {metrics['dataset_size']} | 30 |",
        f"| 成功匹配企业 | {metrics['found_count']} | 30 |",
        f"| 来源可追溯率 | {metrics['source_traceability_rate']}% | 100% |",
        f"| 评分证据链接率 | {metrics['evidence_linkage_rate']}% | 100% |",
        f"| 缺失值非零化完整率 | {metrics['missing_value_integrity_rate']}% | 100% |",
        f"| 无记录风险 UNKNOWN 完整率 | {metrics['risk_unknown_integrity_rate']}% | 100% |",
        f"| 确定性重复率 | {metrics['deterministic_repeat_rate']}% | 100% |",
        "",
        "## 解释",
        "",
        "这份报告证明评分服务遵守数据与证据边界，不证明30家企业都值得招商。",
        "业务准确率、Top-K命中率和转化率需要后续由人工复核标签及CRM结果计算。",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    report = evaluate()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    REPORT_MD.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)
