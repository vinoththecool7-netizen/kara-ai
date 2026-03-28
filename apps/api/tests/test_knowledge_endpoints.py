"""Tests for knowledge base search endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from kara_api.main import create_app
from kara_api.db.connection import get_db_session
from kara_api.config import get_settings
from kara_api.knowledge.search import SearchResult


class TestSearchEndpoint:
    @pytest.fixture
    def app(self):
        app = create_app()

        # Override DB session dependency to avoid requiring a real database
        async def mock_db_session():
            yield AsyncMock()

        # Override settings dependency to avoid loading .env / real config
        def mock_get_settings():
            settings = MagicMock()
            settings.EMBEDDING_PROVIDER = "fake"
            return settings

        app.dependency_overrides[get_db_session] = mock_db_session
        app.dependency_overrides[get_settings] = mock_get_settings
        return app

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    @patch("kara_api.routers.knowledge.hybrid_search", new_callable=AsyncMock)
    @patch("kara_api.routers.knowledge.get_embedding_provider")
    async def test_search_returns_200(self, mock_provider, mock_search, client):
        mock_search.return_value = [
            SearchResult(id=1, section_number="80C", title="Section 80C", score=0.95)
        ]
        response = await client.post(
            "/api/v1/knowledge/search",
            json={"query": "deduction under 80C", "k": 5},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_validates_empty_query(self, client):
        response = await client.post(
            "/api/v1/knowledge/search",
            json={"query": "", "k": 5},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch("kara_api.routers.knowledge.hybrid_search", new_callable=AsyncMock)
    @patch("kara_api.routers.knowledge.get_embedding_provider")
    async def test_search_response_structure(self, mock_provider, mock_search, client):
        mock_search.return_value = [
            SearchResult(id=1, section_number="80C", title="Section 80C", score=0.9)
        ]
        response = await client.post(
            "/api/v1/knowledge/search",
            json={"query": "tax saving", "k": 3},
        )
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "tax saving"
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    @patch("kara_api.routers.knowledge.hybrid_search", new_callable=AsyncMock)
    @patch("kara_api.routers.knowledge.get_embedding_provider")
    async def test_search_respects_k_parameter(self, mock_provider, mock_search, client):
        mock_search.return_value = []
        response = await client.post(
            "/api/v1/knowledge/search",
            json={"query": "NPS deduction", "k": 3},
        )
        assert response.status_code == 200
        # Verify hybrid_search was called with k=3
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args.kwargs.get("k") == 3 or (
            len(call_args.args) > 1 and call_args.args[1] == 3
        )
