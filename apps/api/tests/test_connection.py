"""Unit tests for the database connection module lifecycle."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kara_api.db import connection
from kara_api.db.connection import close_db, get_session_factory, init_db


@pytest.fixture(autouse=True)
async def reset_db_state():
    """Ensure clean module state before and after each test."""
    await close_db()
    yield
    await close_db()


def test_get_session_factory_before_init_raises():
    with pytest.raises(RuntimeError, match="Database not initialized"):
        get_session_factory()


@patch("kara_api.db.connection.create_async_engine")
async def test_init_db_sets_engine(mock_create_engine):
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    await init_db("postgresql+asyncpg://test:test@localhost/test")

    assert connection._engine is not None
    assert connection._session_factory is not None
    mock_create_engine.assert_called_once()


@patch("kara_api.db.connection.create_async_engine")
async def test_close_db_clears_state(mock_create_engine):
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    await init_db("postgresql+asyncpg://test:test@localhost/test")
    assert connection._engine is not None

    await close_db()
    assert connection._engine is None
    assert connection._session_factory is None
    mock_engine.dispose.assert_awaited_once()


@patch("kara_api.db.connection.create_async_engine")
async def test_init_db_creates_session_factory(mock_create_engine):
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine

    await init_db("postgresql+asyncpg://test:test@localhost/test")

    factory = get_session_factory()
    assert factory is not None
