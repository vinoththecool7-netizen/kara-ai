"""Tests for the first-run setup wizard endpoints."""

import httpx
import pytest

from kara_api.config import get_settings
from kara_api.routers import setup as setup_api


@pytest.fixture(autouse=True)
def unconfigured_env(monkeypatch):
    """Simulate a fresh install: no key, default provider, no DB overrides.

    setenv("", ...) rather than delenv: pydantic-settings also reads
    apps/api/.env, and only a real (even empty) env var overrides it.
    """
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()

    async def no_overrides() -> dict:
        return {}

    monkeypatch.setattr(setup_api, "get_runtime_overrides", no_overrides)

    async def no_ollama(settings) -> dict:
        return {"reachable": False, "base_url": "", "models": []}

    monkeypatch.setattr(setup_api, "_detect_ollama", no_ollama)
    yield
    get_settings.cache_clear()


async def test_status_unconfigured(client):
    resp = await client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["source"] is None
    assert body["api_key_masked"] == ""


async def test_status_env_locked(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-verylongtestkey9876")
    get_settings.cache_clear()
    resp = await client.get("/api/v1/setup/status")
    body = resp.json()
    assert body["configured"] is True
    assert body["source"] == "env"
    assert body["api_key_masked"] == "••••9876"
    assert "sk-verylongtestkey9876" not in resp.text


async def test_status_db_configured(client, monkeypatch):
    async def overrides() -> dict:
        return {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "sk-ant-key-4321"}

    monkeypatch.setattr(setup_api, "get_runtime_overrides", overrides)
    resp = await client.get("/api/v1/setup/status")
    body = resp.json()
    assert body["configured"] is True
    assert body["source"] == "db"
    assert body["provider"] == "anthropic"
    assert body["api_key_masked"] == "••••4321"


async def test_save_rejected_when_env_locked(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    get_settings.cache_clear()
    resp = await client.post(
        "/api/v1/setup", json={"provider": "openai", "api_key": "sk-x"}
    )
    assert resp.status_code == 409


async def test_save_validates_then_persists(client, monkeypatch):
    saved: dict = {}

    async def fake_save(values: dict) -> None:
        saved.update(values)

    async def ok_validate(provider, api_key, model, base_url, ollama_base_url):
        return True, "Connection OK."

    monkeypatch.setattr(setup_api, "save_runtime_config", fake_save)
    monkeypatch.setattr(setup_api, "_validate", ok_validate)

    resp = await client.post(
        "/api/v1/setup",
        json={"provider": "openai", "api_key": "sk-new-key-1234", "model": ""},
    )
    assert resp.status_code == 200
    assert saved["LLM_PROVIDER"] == "openai"
    assert saved["LLM_API_KEY"] == "sk-new-key-1234"
    assert saved["LLM_MODEL"] == "gpt-4o"  # default filled in
    # true-OpenAI setups also get embeddings configured
    assert saved["EMBEDDING_PROVIDER"] == "openai"
    assert "sk-new-key-1234" not in resp.text


async def test_save_rejects_invalid_credentials(client, monkeypatch):
    async def bad_validate(provider, api_key, model, base_url, ollama_base_url):
        return False, "Invalid API key."

    monkeypatch.setattr(setup_api, "_validate", bad_validate)
    resp = await client.post(
        "/api/v1/setup", json={"provider": "openai", "api_key": "sk-bad"}
    )
    assert resp.status_code == 400


async def test_test_endpoint_reports_result(client, monkeypatch):
    async def ok_validate(provider, api_key, model, base_url, ollama_base_url):
        return True, "Connection OK."

    monkeypatch.setattr(setup_api, "_validate", ok_validate)
    resp = await client.post(
        "/api/v1/setup/test", json={"provider": "openai", "api_key": "sk-x"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "message": "Connection OK."}


class TestValidate:
    """_validate against a mocked httpx transport."""

    def _client(self, handler) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def test_openai_valid(self):
        def handler(request):
            assert request.headers["Authorization"] == "Bearer sk-good"
            return httpx.Response(200, json={"data": []})

        ok, _ = await setup_api._validate(
            "openai", "sk-good", "gpt-4o", "", "", client=self._client(handler)
        )
        assert ok is True

    async def test_openai_bad_key(self):
        def handler(request):
            return httpx.Response(401, json={"error": "bad key"})

        ok, message = await setup_api._validate(
            "openai", "sk-bad", "gpt-4o", "", "", client=self._client(handler)
        )
        assert ok is False
        assert "key" in message.lower()

    async def test_ollama_reachable(self):
        def handler(request):
            return httpx.Response(200, json={"models": [{"name": "llama3.1:latest"}]})

        ok, _ = await setup_api._validate(
            "ollama",
            "",
            "llama3.1",
            "",
            "http://ollama:11434",
            client=self._client(handler),
        )
        assert ok is True
