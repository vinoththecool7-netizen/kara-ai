import os

import pytest
from httpx import ASGITransport, AsyncClient

from kara_api.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Database integration fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def database_url():
    """PostgreSQL URL for integration tests. Set TEST_DATABASE_URL to override."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://kara:kara@localhost:5432/kara_test",
    )


@pytest.fixture(scope="session")
def sync_database_url(database_url):
    """Synchronous version of the database URL (for Alembic)."""
    return database_url.replace("+asyncpg", "")


@pytest.fixture
async def db_session(database_url):
    """Yield an async session connected to the test database."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
