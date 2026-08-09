from types import SimpleNamespace

import pytest

import app.core.llm_gateway as gateway_module


def _settings(**overrides):
    values = {
        "deepseek_api_key": "deepseek-test-key",
        "deepseek_base_url": "https://api.deepseek.com/v1",
        "deepseek_model": "deepseek-v4-pro",
        "openai_api_key": "",
        "openai_model": "gpt-4o",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_gateway_uses_configured_openai_model_without_hardcoded_fallback(monkeypatch):
    settings = _settings(
        deepseek_api_key="",
        openai_api_key="openai-test-key-that-is-long-enough",
        openai_model="configured-openai-model",
    )
    monkeypatch.setattr(gateway_module, "get_settings", lambda: settings)

    gateway = gateway_module.LLMGateway()

    assert gateway._available_models == ["configured-openai-model"]
    assert gateway._models_for_task("simple") == [
        "deepseek-v4-pro",
        "configured-openai-model",
    ]


@pytest.mark.asyncio
async def test_gateway_validates_deepseek_model_with_models_endpoint(monkeypatch):
    monkeypatch.setattr(gateway_module, "get_settings", lambda: _settings())

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "deepseek-v4-flash"},
                    {"id": "deepseek-v4-pro"},
                ]
            }

    class Client:
        def __init__(self, *args, **kwargs):
            self.requested_url = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers):
            assert url == "https://api.deepseek.com/v1/models"
            assert headers["Authorization"].startswith("Bearer ")
            return Response()

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    gateway = gateway_module.LLMGateway()
    report = await gateway.validate_configured_models()

    assert report["providers"]["deepseek"] == {
        "status": "ready",
        "model": "deepseek-v4-pro",
    }
