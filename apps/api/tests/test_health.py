import pytest


@pytest.mark.asyncio
async def test_health_degraded_without_database(client):
    """In unit tests no DB is initialized — health reports degraded (503)."""
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}


@pytest.mark.asyncio
async def test_health_content_type(client):
    response = await client.get("/health")
    assert "application/json" in response.headers["content-type"]
