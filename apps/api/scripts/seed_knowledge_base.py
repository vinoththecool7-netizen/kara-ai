"""Seed script: populate the tax_sections and section_relationships tables.

Usage:
    python scripts/seed_knowledge_base.py
    python scripts/seed_knowledge_base.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Path bootstrap — allow running as `python scripts/seed_knowledge_base.py`
# from the apps/api directory without installing the package.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from kara_api.config import get_settings  # noqa: E402  (after sys.path manipulation)
from kara_api.knowledge.embeddings import get_embedding_provider  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tax_sections.yaml"
BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_embedding_text(section: dict) -> str:
    """Concatenate fields into the text that will be embedded."""
    parts = [section["title"], section["content"]]

    summary = section.get("summary")
    if summary:
        parts.append(summary)

    common_questions = section.get("common_questions")
    if common_questions:
        parts.append(" ".join(common_questions))

    return "\n".join(parts)


def load_yaml() -> dict:
    """Load and parse the tax_sections.yaml data file."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")
    with DATA_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_yaml(data: dict) -> None:
    """Basic structural validation of the YAML data."""
    if "sections" not in data:
        raise ValueError("YAML is missing top-level 'sections' key")

    required_fields = {"section_number", "ltree_path", "title", "content"}
    for idx, section in enumerate(data["sections"]):
        missing = required_fields - set(section.keys())
        if missing:
            raise ValueError(
                f"Section at index {idx} is missing required fields: {missing}"
            )

    logger.info(
        "Validation passed: %d sections, %d relationships",
        len(data.get("sections", [])),
        len(data.get("relationships", [])),
    )


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------


async def generate_embeddings(
    sections: list[dict], provider, dry_run: bool
) -> list[list[float] | None]:
    """Generate embeddings for all sections in batches of BATCH_SIZE."""
    if dry_run:
        logger.info("[dry-run] Skipping embedding generation for %d sections", len(sections))
        return [None] * len(sections)

    texts = [build_embedding_text(s) for s in sections]
    embeddings: list[list[float]] = []

    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(texts))
        batch = texts[start:end]

        logger.info(
            "Generating embeddings: batch %d/%d (%d texts)",
            batch_idx + 1,
            total_batches,
            len(batch),
        )
        batch_embeddings = await provider.embed(batch)
        embeddings.extend(batch_embeddings)

    logger.info("Generated %d embeddings total", len(embeddings))
    return embeddings


async def seed(dry_run: bool = False) -> None:
    """Main seeding coroutine."""
    settings = get_settings()

    # ------------------------------------------------------------------
    # Load and validate data
    # ------------------------------------------------------------------
    logger.info("Loading data from %s", DATA_FILE)
    data = load_yaml()
    validate_yaml(data)

    sections: list[dict] = data.get("sections", [])
    relationships: list[dict] = data.get("relationships", [])

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    provider = get_embedding_provider(settings)
    logger.info(
        "Using embedding provider: %s", settings.EMBEDDING_PROVIDER
    )
    embeddings = await generate_embeddings(sections, provider, dry_run)

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------
    if dry_run:
        logger.info("[dry-run] Would insert %d sections and %d relationships", len(sections), len(relationships))
        logger.info("[dry-run] Dry run complete — no DB writes performed")
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    try:
        async with engine.begin() as conn:
            # ----------------------------------------------------------
            # Idempotency: TRUNCATE first
            # ----------------------------------------------------------
            logger.info("Truncating tax_sections CASCADE...")
            await conn.execute(text("TRUNCATE TABLE tax_sections CASCADE"))

            # ----------------------------------------------------------
            # Insert sections
            # ----------------------------------------------------------
            logger.info("Inserting %d sections...", len(sections))

            section_number_to_id: dict[str, int] = {}

            for idx, (section, embedding) in enumerate(zip(sections, embeddings)):
                section_number = section["section_number"]
                ltree_path = section["ltree_path"]
                title = section["title"]
                content = section["content"]
                summary = section.get("summary")
                common_questions = section.get("common_questions") or []

                # Build metadata_json — store common_questions and any
                # extra fields not part of the core schema.
                metadata = {}
                if common_questions:
                    metadata["common_questions"] = common_questions
                # Carry through any extra keys from YAML (future-proofing)
                known_keys = {
                    "section_number", "ltree_path", "title", "content",
                    "summary", "common_questions",
                }
                for key, value in section.items():
                    if key not in known_keys:
                        metadata[key] = value

                # Represent the embedding as a pgvector-compatible string
                embedding_value = str(embedding) if embedding is not None else None

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
                        "section_number": section_number,
                        "ltree_path": ltree_path,
                        "title": title,
                        "content": content,
                        "summary": summary,
                        "embedding": embedding_value,
                        "metadata_json": json.dumps(metadata),
                    },
                )
                row = result.fetchone()
                section_number_to_id[section_number] = row[0]

                if (idx + 1) % 10 == 0 or (idx + 1) == len(sections):
                    logger.info("  Inserted %d/%d sections", idx + 1, len(sections))

            # ----------------------------------------------------------
            # Insert relationships
            # ----------------------------------------------------------
            logger.info("Inserting %d relationships...", len(relationships))

            skipped = 0
            inserted = 0
            for rel in relationships:
                parent_num = rel["parent"]
                child_num = rel["child"]
                rel_type = rel["type"]

                parent_id = section_number_to_id.get(parent_num)
                child_id = section_number_to_id.get(child_num)

                if parent_id is None:
                    logger.warning(
                        "Skipping relationship: unknown parent section_number '%s'",
                        parent_num,
                    )
                    skipped += 1
                    continue

                if child_id is None:
                    logger.warning(
                        "Skipping relationship: unknown child section_number '%s'",
                        child_num,
                    )
                    skipped += 1
                    continue

                await conn.execute(
                    text(
                        """
                        INSERT INTO section_relationships
                            (parent_id, child_id, relationship_type)
                        VALUES
                            (:parent_id, :child_id, :relationship_type)
                        ON CONFLICT (parent_id, child_id, relationship_type) DO NOTHING
                        """
                    ),
                    {
                        "parent_id": parent_id,
                        "child_id": child_id,
                        "relationship_type": rel_type,
                    },
                )
                inserted += 1

            if skipped:
                logger.warning(
                    "Skipped %d relationships due to unknown section numbers", skipped
                )
            logger.info("Inserted %d relationships", inserted)

        logger.info("Seed complete.")

    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the Kara knowledge base from data/tax_sections.yaml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate data and generate embeddings without writing to the database",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed(dry_run=args.dry_run))
