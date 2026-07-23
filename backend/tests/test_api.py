from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


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


def test_investment_search_returns_complete_cards():
    with TestClient(app) as client:
        response = client.post("/api/v1/investment/search", json={"industry": "机器人"})
        assert response.status_code == 200
        enterprises = response.json()["data"]["enterprises"]
        assert len(enterprises) == 5
        assert all(item["name"] and item["location"] and item["match_reason"] for item in enterprises)


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
        assert "产业趋势评分" in body["response"]
        assert "发现 5 家目标企业" in body["response"]

        trace = client.get(f"/api/v1/agent/task/{body['task_id']}/trace")
        assert trace.status_code == 200
        trace_body = trace.json()
        assert len(trace_body["nodes"]) == 5
        assert len(trace_body["steps"]) >= 6
