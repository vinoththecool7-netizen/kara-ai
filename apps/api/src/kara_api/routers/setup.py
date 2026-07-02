"""First-run setup wizard endpoints.

Same trust model as the rest of the unauthenticated API: anyone who can
reach the instance can configure it, and the compose defaults bind to
loopback. API keys are accepted, validated, stored — never echoed back.
"""
from __future__ import annotations

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from kara_api.config import get_settings
from kara_api.runtime_config import (
    get_runtime_overrides,
    is_env_configured,
    mask_key,
    save_runtime_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])

PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.1",
}

# Where a compose-profile or host Ollama may live, tried in order after the
# configured OLLAMA_BASE_URL.
OLLAMA_CANDIDATE_URLS = (
    "http://ollama:11434",
    "http://host.docker.internal:11434",
)


class SetupRequest(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"]
    api_key: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    # OpenAI-compatible base URL (e.g. OpenRouter); empty = provider default.
    base_url: str = Field(default="", max_length=500)
    ollama_base_url: str = Field(default="", max_length=500)


class TestResult(BaseModel):
    ok: bool
    message: str


class OllamaStatus(BaseModel):
    reachable: bool
    base_url: str
    models: list[str]


class SetupStatus(BaseModel):
    configured: bool
    source: Literal["env", "db"] | None
    provider: str
    model: str
    api_key_masked: str
    ollama: OllamaStatus


async def _probe_ollama(
    base_url: str, client: httpx.AsyncClient | None = None
) -> list[str] | None:
    """Model names when an Ollama answers at base_url, else None."""
    if not base_url:
        return None
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=1.5)
    try:
        resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return None
    finally:
        if own_client:
            await client.aclose()


async def _detect_ollama(settings) -> dict:
    """Probe the configured URL, the compose profile, then the docker host."""
    seen: set[str] = set()
    for url in (settings.OLLAMA_BASE_URL, *OLLAMA_CANDIDATE_URLS):
        if not url or url in seen:
            continue
        seen.add(url)
        models = await _probe_ollama(url)
        if models is not None:
            return {"reachable": True, "base_url": url, "models": models}
    return {"reachable": False, "base_url": "", "models": []}


async def _validate(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    ollama_base_url: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, str]:
    """Cheap credential/reachability check; never sends chat content."""
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    try:
        if provider == "openai":
            base = (base_url or "https://api.openai.com/v1").rstrip("/")
            resp = await client.get(
                f"{base}/models", headers={"Authorization": f"Bearer {api_key}"}
            )
            if resp.status_code in (401, 403):
                return False, "Invalid API key."
            resp.raise_for_status()
            return True, "Connection OK."
        if provider == "anthropic":
            resp = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            if resp.status_code in (401, 403):
                return False, "Invalid API key."
            resp.raise_for_status()
            return True, "Connection OK."
        if provider == "ollama":
            models = await _probe_ollama(ollama_base_url, client=client)
            if models is None:
                return False, f"Ollama not reachable at {ollama_base_url}."
            if model and not any(
                m == model or m.startswith(f"{model}:") for m in models
            ):
                return (
                    True,
                    f"Connected, but model '{model}' is not pulled yet — "
                    f"run: ollama pull {model}",
                )
            return True, "Connection OK."
        return False, f"Unknown provider: {provider}"
    except httpx.HTTPStatusError as exc:
        return False, f"Provider returned HTTP {exc.response.status_code}."
    except Exception:
        logger.warning("Setup validation failed", exc_info=True)
        return False, "Could not reach the provider. Check the URL and network."
    finally:
        if own_client:
            await client.aclose()


def _derive_config(body: SetupRequest, default_ollama_url: str) -> dict[str, str]:
    """Turn a wizard submission into runtime_settings rows."""
    model = body.model or PROVIDER_DEFAULT_MODELS[body.provider]
    values: dict[str, str] = {
        "LLM_PROVIDER": body.provider,
        "LLM_API_KEY": body.api_key,
        "LLM_MODEL": model,
        "LLM_BASE_URL": body.base_url,
    }
    if body.provider == "openai" and not body.base_url:
        # True OpenAI key → it also works for embeddings (semantic search).
        values["EMBEDDING_PROVIDER"] = "openai"
        values["EMBEDDING_MODEL"] = "text-embedding-3-small"
    elif body.provider == "ollama":
        values["OLLAMA_BASE_URL"] = body.ollama_base_url or default_ollama_url
        values["EMBEDDING_PROVIDER"] = "ollama"
    # anthropic / OpenRouter: leave embedding config alone — search degrades
    # gracefully to keyword matching.
    return values


@router.get("/status", response_model=SetupStatus)
async def setup_status() -> SetupStatus:
    settings = get_settings()
    if is_env_configured(settings):
        return SetupStatus(
            configured=True,
            source="env",
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            api_key_masked=mask_key(settings.LLM_API_KEY),
            ollama=OllamaStatus(reachable=False, base_url="", models=[]),
        )

    overrides = await get_runtime_overrides()
    configured = (
        bool(overrides.get("LLM_API_KEY")) or overrides.get("LLM_PROVIDER") == "ollama"
    )
    # Ollama detection only matters while choosing a provider; skip the
    # probes (up to ~4.5s of timeouts) once configured.
    ollama = (
        {"reachable": False, "base_url": "", "models": []}
        if configured
        else await _detect_ollama(settings)
    )
    return SetupStatus(
        configured=configured,
        source="db" if configured else None,
        provider=overrides.get("LLM_PROVIDER", settings.LLM_PROVIDER),
        model=overrides.get("LLM_MODEL", settings.LLM_MODEL),
        api_key_masked=mask_key(overrides.get("LLM_API_KEY", "")),
        ollama=OllamaStatus(**ollama),
    )


@router.post("/test", response_model=TestResult)
async def test_connection(body: SetupRequest) -> TestResult:
    settings = get_settings()
    ollama_url = body.ollama_base_url or settings.OLLAMA_BASE_URL
    model = body.model or PROVIDER_DEFAULT_MODELS[body.provider]
    ok, message = await _validate(
        body.provider, body.api_key, model, body.base_url, ollama_url
    )
    return TestResult(ok=ok, message=message)


@router.post("", response_model=SetupStatus)
async def save_setup(body: SetupRequest) -> SetupStatus:
    settings = get_settings()
    if is_env_configured(settings):
        raise HTTPException(
            status_code=409,
            detail="Configuration is managed via .env on this server.",
        )
    ollama_url = body.ollama_base_url or settings.OLLAMA_BASE_URL
    model = body.model or PROVIDER_DEFAULT_MODELS[body.provider]
    ok, message = await _validate(
        body.provider, body.api_key, model, body.base_url, ollama_url
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    values = _derive_config(body, default_ollama_url=ollama_url)
    await save_runtime_config(values)
    logger.info("Setup wizard configured provider=%s model=%s", body.provider, model)
    return SetupStatus(
        configured=True,
        source="db",
        provider=body.provider,
        model=model,
        api_key_masked=mask_key(body.api_key),
        ollama=OllamaStatus(reachable=False, base_url="", models=[]),
    )
