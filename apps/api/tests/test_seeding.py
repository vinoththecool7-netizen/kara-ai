"""Tests for kara_api.knowledge.seeding — startup knowledge-base seeding."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from kara_api.config import Settings
from kara_api.knowledge.seeding import (
    DATA_FILE,
    load_sections_data,
    seed_if_empty,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(section_count: int):
    """Mock AsyncEngine whose .begin() yields a conn.

    The first ``SELECT COUNT(*)`` returns *section_count*; every execute call
    is recorded on ``engine.calls``.
    """
    engine = MagicMock()
    calls: list[str] = []

    async def execute(stmt, params=None):
        sql = str(stmt)
        calls.append(sql)
        result = MagicMock()
        if "COUNT(*)" in sql.upper():
            result.scalar.return_value = section_count
        result.fetchone.return_value = (len(calls),)  # synthetic RETURNING id
        return result

    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=execute)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    engine.begin = MagicMock(return_value=cm)
    engine.calls = calls
    return engine


def _settings() -> Settings:
    return Settings(EMBEDDING_PROVIDER="fake", _env_file=None)


# ---------------------------------------------------------------------------
# Data file
# ---------------------------------------------------------------------------


class TestDataFile:
    def test_data_file_ships_inside_the_package(self):
        """The YAML must live inside kara_api so the built wheel contains it."""
        assert DATA_FILE.exists()
        assert "kara_api" in DATA_FILE.parts

    def test_load_sections_data(self):
        data = load_sections_data()
        assert len(data["sections"]) >= 100
        assert len(data.get("relationships", [])) > 0


# ---------------------------------------------------------------------------
# seed_if_empty
# ---------------------------------------------------------------------------


class TestSeedIfEmpty:
    @pytest.mark.asyncio
    async def test_skips_when_already_populated(self):
        engine = _make_engine(section_count=114)
        seeded = await seed_if_empty(engine, _settings())
        assert seeded is False
        inserts = [c for c in engine.calls if "INSERT INTO tax_sections" in c]
        assert inserts == []

    @pytest.mark.asyncio
    async def test_seeds_when_empty(self):
        engine = _make_engine(section_count=0)
        seeded = await seed_if_empty(engine, _settings())
        assert seeded is True
        inserts = [c for c in engine.calls if "INSERT INTO tax_sections" in c]
        assert len(inserts) >= 100  # one insert per curated section

    @pytest.mark.asyncio
    async def test_seeds_without_embeddings_when_provider_fails(self):
        """A broken embedding backend must not block seeding — sections are
        inserted with NULL embeddings so keyword search still works."""
        engine = _make_engine(section_count=0)

        failing_provider = AsyncMock()
        failing_provider.embed.side_effect = RuntimeError("401 from embeddings API")

        seeded = await seed_if_empty(
            engine, _settings(), embedding_provider=failing_provider
        )
        assert seeded is True
        inserts = [c for c in engine.calls if "INSERT INTO tax_sections" in c]
        assert len(inserts) >= 100
