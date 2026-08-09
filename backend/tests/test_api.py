from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from urllib.parse import urlparse

from app.main import app
from app.core.security import create_refresh_token
from app.langgraph.nodes.supervisor_nodes import result_aggregator_node


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENTERPRISE_SNAPSHOT = BACKEND_ROOT / "data" / "enterprises" / "enterprise_import_clean.json"
POLICY_CATALOG = BACKEND_ROOT / "data" / "policies_gz_gov" / "_catalog.json"


def test_health_check():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_readiness_allows_disabled_optional_services():
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["components"]["database"] == "disabled"
        assert body["components"]["redis"] == "disabled"


def test_login_rejects_bad_password():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401


def test_login_returns_jwt_for_demo_admin():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert response.json()["access_token"]


def test_refresh_token_is_accepted_only_in_request_body():
    token = create_refresh_token("demo-user")
    with TestClient(app) as client:
        query_response = client.post(f"/api/v1/auth/refresh?refresh_token={token}")
        body_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )

    assert query_response.status_code == 422
    assert body_response.status_code == 200
    assert body_response.json()["access_token"]
    assert body_response.json()["refresh_token"]


@pytest.mark.skipif(
    not ENTERPRISE_SNAPSHOT.is_file(),
    reason="optional enterprise snapshot is not distributed with the source release",
)
def test_investment_search_returns_complete_cards():
    with TestClient(app) as client:
        response = client.post("/api/v1/investment/search", json={"industry": "机器人"})
        assert response.status_code == 200
        data = response.json()["data"]
        enterprises = data["enterprises"]
        assert enterprises
        assert data["total"] >= len(enterprises)
        assert data["returned"] == len(enterprises)
        assert data["catalog_total"] >= data["total"]
        assert all(item["name"] and item["location"] and item["match_reason"] for item in enterprises)


@pytest.mark.skipif(
    not POLICY_CATALOG.is_file(),
    reason="optional policy snapshot is not distributed with the source release",
)
def test_policy_search_returns_government_source_evidence():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/policy/search",
            json={"query": "机器人产业扶持", "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["mode"].startswith("crawl4ai")
        assert data["chunks"]
        government_sources = 0
        for item in data["chunks"]:
            if item["metadata"].get("source_type") == "park_private_document":
                assert item["metadata"].get("document_id")
                continue
            source_url = item["metadata"]["source_url"]
            parsed = urlparse(source_url)
            host = (parsed.hostname or "").lower()
            assert parsed.scheme == "https"
            allowed = (
                "gz.gov.cn",
                "gzns.gov.cn",
                "haizhu.gov.cn",
                "huadu.gov.cn",
                "panyu.gov.cn",
                "zc.gov.cn",
            )
            assert any(host == domain or host.endswith(f".{domain}") for domain in allowed)
            government_sources += 1
        assert government_sources >= 1


@pytest.mark.skipif(
    not POLICY_CATALOG.is_file(),
    reason="optional policy snapshot is not distributed with the source release",
)
def test_policy_chat_preserves_government_source_urls():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/chat",
            json={"message": "查询广州科技创新补贴政策并给出政策来源"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["agents_used"] == ["PolicyAgent"]
        assert "## 政策来源" in body["response"]
        assert "https://" in body["response"]
        assert "gz.gov.cn" in body["response"]


def test_single_policy_agent_aggregation_skips_llm(monkeypatch):
    def fail_if_called():
        raise AssertionError("single PolicyAgent result must not invoke the LLM")

    monkeypatch.setattr(
        "app.langgraph.nodes.supervisor_nodes.get_llm_gateway",
        fail_if_called,
    )
    state = {
        "agent_results": {
            "PolicyAgent": {
                "result": {
                    "summary": "匹配 1 条政策：测试政策。",
                    "data": {
                        "policies": [{
                            "title": "测试政策",
                            "source_url": "https://www.gz.gov.cn/example",
                        }],
                    },
                },
            },
        },
        "trace_steps": [],
    }

    result = result_aggregator_node(state)

    assert result["final_response"].startswith("> **公开数据快照**")
    assert "# 政策匹配结果" in result["final_response"]
    assert "## 政策来源" in result["final_response"]
    assert "https://www.gz.gov.cn/example" in result["final_response"]


def test_missing_trace_preserves_not_found_status():
    with TestClient(app) as client:
        response = client.get("/api/v1/agent/task/nonexistent-12345/trace")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found or trace not yet generated"


@pytest.mark.skipif(
    not (ENTERPRISE_SNAPSHOT.is_file() and POLICY_CATALOG.is_file()),
    reason="optional enterprise and policy snapshots are not distributed with the source release",
)
def test_compound_chat_executes_real_agents_and_trace():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/chat",
            json={"message": "分析机器人产业链，推荐招商企业，评估风险并匹配政策"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["agents_used"] == [
            "IndustryAgent", "InvestmentAgent", "RiskAgent", "PolicyAgent"
        ]
        assert "当前公开企业快照检索到" in body["response"]
        assert "尚无权威市场规模与时间序列" in body["response"]
        assert "评分证据不足" in body["response"]
        assert "风险证据不足" in body["response"]
        assert "产业趋势评分 85" not in body["response"]
        assert "5000亿" not in body["response"]

        trace = client.get(f"/api/v1/agent/task/{body['task_id']}/trace")
        assert trace.status_code == 200
        trace_body = trace.json()
        assert len(trace_body["nodes"]) == 5
        assert len(trace_body["steps"]) >= 6
