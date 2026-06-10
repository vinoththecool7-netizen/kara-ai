"""Knowledge-base seeding: load curated tax sections into PostgreSQL.

The curated data ships inside the package (``kara_api/data/tax_sections.yaml``)
so seeding works from an installed wheel. ``seed_if_empty`` is called on app
startup and is a no-op when the table is already populated; the CLI script
``scripts/seed_knowledge_base.py`` wraps ``seed`` for forced re-seeding.

Embeddings are best-effort: when the embedding provider is unavailable
(no API key, OpenRouter-only setups, network failure) sections are inserted
with NULL embeddings — keyword and graph search keep working, and
``hybrid_search`` already degrades to keyword-only.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from kara_api.config import Settings
from kara_api.knowledge.embeddings import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tax_sections.yaml"
BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_sections_data(path: Path = DATA_FILE) -> dict[str, Any]:
    """Load and structurally validate the tax sections YAML."""
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if "sections" not in data:
        raise ValueError("YAML is missing top-level 'sections' key")

    required_fields = {"section_number", "ltree_path", "title", "content"}
    for idx, section in enumerate(data["sections"]):
        missing = required_fields - set(section.keys())
        if missing:
            raise ValueError(f"Section at index {idx} is missing required fields: {missing}")

    return data


def build_embedding_text(section: dict[str, Any]) -> str:
    """Concatenate fields into the text that will be embedded."""
    parts = [section["title"], section["content"]]
    if section.get("summary"):
        parts.append(section["summary"])
    if section.get("common_questions"):
        parts.append(" ".join(section["common_questions"]))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Embeddings (best-effort)
# ---------------------------------------------------------------------------


async def generate_embeddings_or_none(
    sections: list[dict[str, Any]], provider: EmbeddingProvider
) -> list[list[float] | None]:
    """Generate embeddings in batches; on any failure fall back to None.

    A failing embedding backend must never block seeding — sections without
    embeddings still serve keyword and graph search.
    """
    # An OpenAI-style provider without a key can only fail (after retries);
    # skip the round-trips entirely.
    if getattr(provider, "api_key", None) == "":
        logger.warning(
            "No embedding API key configured — seeding without embeddings "
            "(semantic search disabled, keyword search active)"
        )
        return [None] * len(sections)

    texts = [build_embedding_text(s) for s in sections]
    embeddings: list[list[float] | None] = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        batch = texts[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
        try:
            embeddings.extend(await provider.embed(batch))
        except Exception:
            logger.warning(
                "Embedding generation failed on batch %d/%d — seeding without "
                "embeddings (semantic search disabled, keyword search active)",
                batch_idx + 1,
                total_batches,
                exc_info=True,
            )
            return [None] * len(sections)
        logger.info("Generated embeddings: batch %d/%d", batch_idx + 1, total_batches)

    return embeddings


# ---------------------------------------------------------------------------
# Inserts
# ---------------------------------------------------------------------------


async def _insert_all(
    conn: AsyncConnection,
    sections: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    embeddings: list[list[float] | None],
) -> None:
    """Truncate and repopulate tax_sections + section_relationships."""
    await conn.execute(text("TRUNCATE TABLE tax_sections CASCADE"))

    section_number_to_id: dict[str, int] = {}
    known_keys = {
        "section_number", "ltree_path", "title", "content", "summary", "common_questions",
    }

    for section, embedding in zip(sections, embeddings):
        metadata = {k: v for k, v in section.items() if k not in known_keys}
        if section.get("common_questions"):
            metadata["common_questions"] = section["common_questions"]

        result = await conn.execute(
            text(
                """
                INSERT INTO tax_sections
                    (section_number, ltree_path, title, content,
                     summary, embedding, metadata_json)
                VALUES
                    (:section_number, :ltree_path, :title, :content,
                     :summary, :embedding, :metadata_json)
                RETURNING id
                """
            ),
            {
                "section_number": section["section_number"],
                "ltree_path": section["ltree_path"],
                "title": section["title"],
                "content": section["content"],
                "summary": section.get("summary"),
                "embedding": str(embedding) if embedding is not None else None,
                "metadata_json": json.dumps(metadata),
            },
        )
        row = result.fetchone()
        section_number_to_id[section["section_number"]] = row[0]

    skipped = 0
    for rel in relationships:
        parent_id = section_number_to_id.get(rel["parent"])
        child_id = section_number_to_id.get(rel["child"])
        if parent_id is None or child_id is None:
            logger.warning(
                "Skipping relationship %s -> %s: unknown section number",
                rel["parent"],
                rel["child"],
            )
            skipped += 1
            continue
        await conn.execute(
            text(
                """
                INSERT INTO section_relationships
                    (parent_id, child_id, relationship_type)
                VALUES (:parent_id, :child_id, :relationship_type)
                ON CONFLICT (parent_id, child_id, relationship_type) DO NOTHING
                """
            ),
            {"parent_id": parent_id, "child_id": child_id, "relationship_type": rel["type"]},
        )

    logger.info(
        "Seeded %d sections, %d relationships (%d skipped)",
        len(sections),
        len(relationships) - skipped,
        skipped,
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def seed(
    engine: AsyncEngine,
    settings: Settings,
    embedding_provider: EmbeddingProvider | None = None,
) -> None:
    """Force (re)seed the knowledge base, truncating existing data."""
    data = load_sections_data()
    sections = data["sections"]
    relationships = data.get("relationships", [])

    provider = embedding_provider or get_embedding_provider(settings)
    embeddings = await generate_embeddings_or_none(sections, provider)

    async with engine.begin() as conn:
        await _insert_all(conn, sections, relationships, embeddings)


async def seed_if_empty(
    engine: AsyncEngine,
    settings: Settings,
    embedding_provider: EmbeddingProvider | None = None,
) -> bool:
    """Seed the knowledge base only when tax_sections is empty.

    Returns True if seeding ran, False if data was already present.
    Intended to be called from app startup after migrations.
    """
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM tax_sections"))
        count = result.scalar()

    if count:
        logger.info("Knowledge base already seeded (%s sections) — skipping", count)
        return False

    logger.info("Knowledge base empty — seeding from %s", DATA_FILE.name)
    await seed(engine, settings, embedding_provider)
    return True
