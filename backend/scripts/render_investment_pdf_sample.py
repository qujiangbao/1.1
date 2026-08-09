"""Render a stable PDF fixture for visual QA of the online export."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.database.models.investment import InvestmentScenario
from app.services.investment_pdf_service import render_investment_scenario_pdf
from app.services.investment_scoring_service import score_enterprise
from app.tools.adapters.local_json import LocalJsonAdapter


if __name__ == "__main__":
    adapter = LocalJsonAdapter(
        BACKEND_ROOT / "data" / "enterprises" / "enterprise_import_clean.json"
    )
    records = adapter._load()[:2]
    cards = [
        score_enterprise(
            adapter._to_profile(record),
            industry="人工智能",
            target_chain_roles=["人工智能", "工业软件", "系统集成"],
            data_mode="real",
        )
        for record in records
    ]
    scenario = InvestmentScenario(
        id="pdf-visual-qa",
        name="广州人工智能产业招商研判",
        industry="人工智能",
        target_chain_roles=["人工智能", "工业软件", "系统集成"],
        location_preference="广州",
        result_limit=2,
        data_mode="real",
        status="READY",
        recommendation_snapshot=[
            card.model_dump(mode="json")
            for card in cards
        ],
        snapshot_metadata={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "investment-score-v1.0",
            "orchestration_version": "investment-decision-graph-v1.0",
            "limitations": [
                "融资、招聘、扩产和落地意愿数据覆盖不足。",
                "没有真实风险事件时风险等级保持 UNKNOWN。",
            ],
        },
        created_by="visual-qa",
    )
    target = BACKEND_ROOT / "output" / "pdf" / "investment-report-sample.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(render_investment_scenario_pdf(scenario))
    print(target)
