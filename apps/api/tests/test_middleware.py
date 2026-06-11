"""Tests for security headers, request IDs, the global exception handler,
and the DB-checking health endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def bare_client():
    """Client against the real app with a noop lifespan (no DB)."""
    from contextlib import asynccontextmanager

    from kara_api.main import create_app

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    with patch("kara_api.main.lifespan", _noop_lifespan):
        app = create_app()
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, app


class TestSecurityHeaders:
    async def test_standard_headers_present(self, bare_client):
        client, _ = bare_client
        resp = await client.get("/health")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "no-referrer"


class TestRequestID:
    async def test_request_id_generated(self, bare_client):
        client, _ = bare_client
        resp = await client.get("/health")
        assert len(resp.headers["x-request-id"]) >= 8

    async def test_request_id_echoed_when_supplied(self, bare_client):
        client, _ = bare_client
        resp = await client.get("/health", headers={"X-Request-ID": "req-12345"})
        assert resp.headers["x-request-id"] == "req-12345"


class TestGlobalExceptionHandler:
    async def test_unhandled_errors_return_generic_500(self, bare_client):
        client, app = bare_client

        @app.get("/boom")
        async def boom():  # pragma: no cover - exercised via HTTP
            raise RuntimeError("secret stacktrace detail")

        resp = await client.get("/boom")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal server error"}
        assert "secret" not in resp.text


class TestHealth:
    async def test_health_degraded_without_db(self, bare_client):
        """No initialized engine -> 503 so orchestrators mark us unhealthy."""
        client, _ = bare_client
        resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"
        assert resp.json()["database"] == "unavailable"

    async def test_health_ok_with_db(self, bare_client):
        client, _ = bare_client

        conn = AsyncMock()
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        engine = MagicMock()
        engine.connect = MagicMock(return_value=cm)

        with patch("kara_api.main.get_engine", return_value=engine):
            resp = await client.get("/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "database": "ok"}
