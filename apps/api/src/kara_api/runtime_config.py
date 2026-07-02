"""DB-backed runtime configuration written by the first-run setup wizard.

Precedence: when the environment already configures an LLM (an API key, or
a keyless provider like ollama/fake), env is the sole source of truth and
the wizard is disabled. Otherwise rows in the runtime_settings table are
overlaid onto the env settings.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from kara_api.config import Settings, get_settings

logger = logging.getLogger(__name__)

# The only keys the wizard may read or write.
WIZARD_KEYS = frozenset(
    {
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_BASE_URL",
        "OLLAMA_BASE_URL",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
    }
)


def is_env_configured(settings: Settings) -> bool:
    """True when the environment already configures an LLM (wizard disabled)."""
    return bool(settings.LLM_API_KEY) or settings.LLM_PROVIDER.lower() in (
        "ollama",
        "fake",
    )


def mask_key(key: str) -> str:
    """Mask an API key for display; never return the full key anywhere."""
    if not key:
        return ""
    if len(key) <= 8:
        return "••••"
    return f"••••{key[-4:]}"


def apply_overrides(settings: Settings, overrides: dict[str, str]) -> Settings:
    """Overlay wizard-managed values onto a Settings copy."""
    updates = {k: v for k, v in overrides.items() if k in WIZARD_KEYS}
    if not updates:
        return settings
    return settings.model_copy(update=updates)


async def get_runtime_overrides() -> dict[str, str]:
    """Read wizard-written rows; empty dict when none exist."""
    from kara_api.db.connection import get_session_factory
    from kara_api.db.models import RuntimeSetting

    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(RuntimeSetting))).scalars().all()
        return {r.key: r.value for r in rows if r.key in WIZARD_KEYS}


async def get_effective_settings() -> Settings:
    """Env settings, overlaid with wizard config unless env-configured.

    A DB failure degrades to env settings rather than breaking chat.
    """
    settings = get_settings()
    if is_env_configured(settings):
        return settings
    try:
        overrides = await get_runtime_overrides()
    except Exception:
        logger.exception("Failed to load runtime settings; using env settings")
        return settings
    return apply_overrides(settings, overrides)


async def save_runtime_config(values: dict[str, str]) -> None:
    """Upsert wizard values; rejects keys outside WIZARD_KEYS."""
    from kara_api.db.connection import get_session_factory
    from kara_api.db.models import RuntimeSetting

    unknown = set(values) - WIZARD_KEYS
    if unknown:
        raise ValueError(f"Refusing to store non-wizard keys: {sorted(unknown)}")

    factory = get_session_factory()
    async with factory() as session:
        for key, value in values.items():
            stmt = (
                insert(RuntimeSetting)
                .values(key=key, value=value)
                .on_conflict_do_update(index_elements=["key"], set_={"value": value})
            )
            await session.execute(stmt)
        await session.commit()
