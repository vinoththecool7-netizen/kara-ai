"""CLI wrapper: force (re)seed the knowledge base.

The seeding logic lives in ``kara_api.knowledge.seeding`` (it also runs
automatically at app startup when the table is empty). Use this script to
force a re-seed after editing ``kara_api/data/tax_sections.yaml``.

Usage:
    python scripts/seed_knowledge_base.py
    python scripts/seed_knowledge_base.py --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

# Allow running uninstalled from the apps/api directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from kara_api.config import get_settings  # noqa: E402
from kara_api.knowledge.seeding import load_sections_data, seed  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main(dry_run: bool) -> None:
    settings = get_settings()

    if dry_run:
        data = load_sections_data()
        logger.info(
            "[dry-run] Validation passed: %d sections, %d relationships — no DB writes",
            len(data["sections"]),
            len(data.get("relationships", [])),
        )
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        await seed(engine, settings)
        logger.info("Seed complete.")
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Force (re)seed the Kara knowledge base")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate the data file without writing to the database",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args().dry_run))
