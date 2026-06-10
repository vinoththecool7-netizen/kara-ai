"""Integration tests for Alembic migrations.

These tests require a running PostgreSQL instance. They verify that
``alembic upgrade head`` creates all tables, extensions, and indexes.

Set TEST_DATABASE_URL to point to a test database, or use the default
``postgresql+asyncpg://kara:kara@localhost:5432/kara_test``.
"""

import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration


def _run_alembic(command: str, database_url: str) -> None:
    """Run an alembic command programmatically."""
    import os

    from alembic.config import Config

    from alembic import command as alembic_cmd

    # Set env var so get_settings() in env.py picks up the test URL
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url

    # Clear the lru_cache so Settings re-reads from env
    from kara_api.config import get_settings
    get_settings.cache_clear()

    try:
        cfg = Config("alembic.ini")
        cfg.set_main_option("script_location", "alembic")
        getattr(alembic_cmd, command)(cfg, "head" if command == "upgrade" else "base")
    finally:
        # Restore original env
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url
        get_settings.cache_clear()


@pytest.fixture(scope="module")
def _apply_migrations(database_url):
    """Apply migrations before the module, downgrade after."""
    import os

    original_dir = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    try:
        _run_alembic("upgrade", database_url)
        yield
        _run_alembic("downgrade", database_url)
    finally:
        os.chdir(original_dir)


@pytest.fixture
async def engine(database_url):
    eng = create_async_engine(database_url, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_apply_migrations")
class TestMigration:
    """All migration integration tests."""

    async def test_all_tables_exist(self, engine):
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        expected = {"tax_sections", "section_relationships", "sessions", "messages", "alembic_version"}
        assert expected.issubset(set(tables)), f"Missing tables: {expected - set(tables)}"

    async def test_pgvector_extension_enabled(self, session: AsyncSession):
        result = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        assert result.scalar() == "vector"

    async def test_ltree_extension_enabled(self, session: AsyncSession):
        result = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'ltree'")
        )
        assert result.scalar() == "ltree"

    async def test_indexes_exist(self, session: AsyncSession):
        result = await session.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
        )
        index_names = {row[0] for row in result.fetchall()}
        expected = {
            "ix_tax_sections_search_vector",
            "ix_tax_sections_ltree_path",
            "ix_tax_sections_embedding",
            "ix_messages_session_created",
            "ix_sessions_updated_at",
        }
        assert expected.issubset(index_names), f"Missing indexes: {expected - index_names}"

    async def test_insert_tax_section_generates_tsvector(self, session: AsyncSession):
        await session.execute(
            text(
                "INSERT INTO tax_sections (section_number, ltree_path, title, content) "
                "VALUES (:num, :path, :title, :content)"
            ),
            {
                "num": "80C_test",
                "path": "income_tax.deductions.80c",
                "title": "Section 80C Deductions",
                "content": "Investment deductions up to 1.5 lakh under old regime",
            },
        )
        await session.commit()

        result = await session.execute(
            text("SELECT search_vector FROM tax_sections WHERE section_number = '80C_test'")
        )
        sv = result.scalar()
        assert sv is not None, "search_vector should be auto-generated"
        assert "deduct" in str(sv), "tsvector should contain stemmed 'deductions'"

        # Cleanup
        await session.execute(text("DELETE FROM tax_sections WHERE section_number = '80C_test'"))
        await session.commit()

    async def test_session_message_cascade_delete(self, session: AsyncSession):
        session_id = uuid.uuid4()

        await session.execute(
            text("INSERT INTO sessions (id) VALUES (:id)"),
            {"id": session_id},
        )
        await session.execute(
            text(
                "INSERT INTO messages (session_id, role, content) "
                "VALUES (:sid, 'user', 'hello')"
            ),
            {"sid": session_id},
        )
        await session.commit()

        # Verify message exists
        result = await session.execute(
            text("SELECT count(*) FROM messages WHERE session_id = :sid"),
            {"sid": session_id},
        )
        assert result.scalar() == 1

        # Delete session — message should cascade
        await session.execute(
            text("DELETE FROM sessions WHERE id = :id"),
            {"id": session_id},
        )
        await session.commit()

        result = await session.execute(
            text("SELECT count(*) FROM messages WHERE session_id = :sid"),
            {"sid": session_id},
        )
        assert result.scalar() == 0, "Messages should be cascade-deleted with session"

    async def test_section_relationship_unique_constraint(self, session: AsyncSession):
        # Insert two sections
        await session.execute(
            text(
                "INSERT INTO tax_sections (section_number, ltree_path, title, content) VALUES "
                "('80C_uc', 'income_tax.deductions.80c', 'Section 80C', 'Deductions'), "
                "('80CCD_uc', 'income_tax.deductions.80ccd', 'Section 80CCD', 'NPS')"
            )
        )
        await session.commit()

        result = await session.execute(
            text("SELECT id FROM tax_sections WHERE section_number IN ('80C_uc', '80CCD_uc') ORDER BY id")
        )
        ids = [row[0] for row in result.fetchall()]
        parent_id, child_id = ids[0], ids[1]

        # Insert relationship
        await session.execute(
            text(
                "INSERT INTO section_relationships (parent_id, child_id, relationship_type) "
                "VALUES (:pid, :cid, 'supplements')"
            ),
            {"pid": parent_id, "cid": child_id},
        )
        await session.commit()

        # Duplicate should fail

        with pytest.raises(Exception):
            await session.execute(
                text(
                    "INSERT INTO section_relationships (parent_id, child_id, relationship_type) "
                    "VALUES (:pid, :cid, 'supplements')"
                ),
                {"pid": parent_id, "cid": child_id},
            )
            await session.commit()

        await session.rollback()

        # Cleanup
        await session.execute(
            text("DELETE FROM tax_sections WHERE section_number IN ('80C_uc', '80CCD_uc')")
        )
        await session.commit()
