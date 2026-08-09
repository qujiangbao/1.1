from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.runtime_metrics import get_runtime_metrics


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENTERPRISE_SNAPSHOT = BACKEND_ROOT / "data" / "enterprises" / "enterprise_import_clean.json"
POLICY_CATALOG = BACKEND_ROOT / "data" / "policies_gz_gov" / "_catalog.json"
PARK_DOCUMENT_INDEX = BACKEND_ROOT / "data" / "park_documents" / "index.json"


def test_team_status_uses_real_runtime_events_without_database():
    metrics = get_runtime_metrics()
    metrics.reset_for_tests()
    started = metrics.begin("PolicyAgent", "policy-task-1")
    metrics.finish("PolicyAgent", "policy-task-1", "success", started, 42)

    with TestClient(app) as client:
        response = client.get("/api/v1/agent/team/status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["metrics_source"] == "runtime"
    assert data["total_tasks_today"] == 1
    assert data["success_rate"] == 100.0
    assert data["agents"]["PolicyAgent"]["last_task"] == "policy-task-1"
    assert data["agents"]["PolicyAgent"]["last_execution_ms"] >= 42


def test_team_status_exposes_running_agent():
    metrics = get_runtime_metrics()
    metrics.reset_for_tests()
    started = metrics.begin("RiskAgent", "risk-task-active")

    try:
        with TestClient(app) as client:
            data = client.get("/api/v1/agent/team/status").json()["data"]
        assert data["running_agents"] == 1
        assert data["agents"]["RiskAgent"]["status"] == "running"
        assert data["agents"]["RiskAgent"]["last_task"] == "risk-task-active"
    finally:
        metrics.finish("RiskAgent", "risk-task-active", "success", started, 1)


@pytest.mark.skipif(
    not (ENTERPRISE_SNAPSHOT.is_file() and POLICY_CATALOG.is_file()),
    reason="optional enterprise and policy snapshots are not distributed with the source release",
)
def test_dashboard_uses_local_snapshots_without_faking_investment_funnel():
    get_runtime_metrics().reset_for_tests()

    with TestClient(app) as client:
        overview = client.get("/api/v1/dashboard/overview")
        bi = client.get("/api/v1/dashboard/bi")

    assert overview.status_code == 200
    overview_data = overview.json()["data"]
    assert overview_data["park_overview"]["total_enterprises"] >= 744
    assert overview_data["policy"]["total"] >= 222
    assert overview_data["investment"]["opportunities"] == 0
    assert overview_data["investment"]["data_available"] is False
    assert overview_data["metadata"]["business_data_available"] is True
    assert overview_data["metadata"]["business_data_mode"] == "local_snapshot"

    assert bi.status_code == 200
    bi_data = bi.json()["data"]
    assert bi_data["industry_distribution"]
    assert bi_data["metadata"]["business_data_available"] is True
    assert bi_data["metadata"]["investment_funnel_data_available"] is False
    assert bi_data["metadata"]["investment_funnel_source"] is None
    assert "investment_funnel" in bi_data["metadata"]["unavailable_metrics"]
    assert bi_data["kpi_cards"][1]["trend"] == "业务表尚未接入"


@pytest.mark.skipif(
    not PARK_DOCUMENT_INDEX.is_file(),
    reason="private park documents are not distributed with the source release",
)
def test_risk_dashboard_uses_imported_evidence_without_demo_substitution():
    with TestClient(app) as client:
        response = client.get("/api/v1/dashboard/risk")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_enterprises"] >= 744
    assert data["evaluated_enterprises"] >= 1
    assert sum(data["distribution"].values()) == data["evaluated_enterprises"]
    assert data["enterprises"]
    assert all(item["event_count"] >= 1 for item in data["enterprises"])
    assert data["data_available"] is True
    assert data["is_demo"] is False
    assert data["source"] == "park_document_evidence"


def test_demo_mode_is_explicit_and_coherent_across_dashboards():
    with TestClient(app) as client:
        overview = client.get("/api/v1/dashboard/overview?mode=demo")
        bi = client.get("/api/v1/dashboard/bi?mode=demo")
        risk = client.get("/api/v1/dashboard/risk?mode=demo")
        report = client.get("/api/v1/agent/daily-report?mode=demo")

    assert overview.status_code == 200
    overview_data = overview.json()["data"]
    assert overview_data["metadata"]["is_demo"] is True
    assert "非真实经营数据" in overview_data["metadata"]["disclaimer"]
    assert overview_data["park_overview"]["total_enterprises"] == 36
    assert sum(overview_data["risk"].values()) == 36

    bi_data = bi.json()["data"]
    assert bi_data["metadata"]["is_demo"] is True
    assert bi_data["metadata"]["investment_funnel_data_available"] is True
    assert bi_data["investment_funnel"][0]["count"] == 36
    assert bi_data["investment_funnel"][-1]["count"] == 2

    risk_data = risk.json()["data"]
    assert risk_data["is_demo"] is True
    assert risk_data["evaluated_enterprises"] == 5
    assert sum(risk_data["distribution"].values()) == 5
    assert all(item["name"].startswith("示例招商企业-") for item in risk_data["enterprises"])

    report_data = report.json()["data"]
    assert report_data["metadata"]["is_demo"] is True
    assert report_data["investment"]["data_available"] is True
