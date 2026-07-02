# Frictionless Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docker compose up -d` with zero file edits boots Kara from prebuilt GHCR images into a browser setup wizard; `--profile local` adds a fully offline Ollama stack.

**Architecture:** A CI job publishes multi-arch images to GHCR; the default compose file pulls them (`.env` optional). A new DB-backed runtime-config layer (`runtime_settings` table) is overlaid onto env settings unless env explicitly configures an LLM; a `/api/v1/setup` router exposes status/test/save; the Next.js app gains a `/setup` wizard page and a redirect guard in `ChatLayout`.

**Tech Stack:** GitHub Actions + buildx/GHCR, Docker Compose profiles, FastAPI + SQLAlchemy 2.0 + Alembic, pydantic-settings, Next.js 16 (App Router) + vitest/Testing Library.

Spec: `docs/superpowers/specs/2026-07-02-frictionless-setup-design.md`

**Working-tree note:** the repo has in-flight *uncommitted* security-hardening changes. Commit ONLY the files each task names (`git add <paths>`), never `git add -A`.

---

### Task 1: CI publish job → GHCR

**Files:**
- Modify: `.github/workflows/ci.yml` (append job)

- [ ] **Step 1: Append `publish` job to ci.yml**

```yaml
  publish:
    name: Publish images (GHCR)
    if: github.event_name == 'push' && github.ref == 'refs/heads/master'
    needs: [tax-engine, api, web, smoke]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Compute short SHA
        id: sha
        run: echo "short=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"
      - name: Build and push API image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/api/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ghcr.io/vinoththecool7-netizen/kara-api:latest
            ghcr.io/vinoththecool7-netizen/kara-api:sha-${{ steps.sha.outputs.short }}
          cache-from: type=gha,scope=api
          cache-to: type=gha,mode=max,scope=api
      - name: Build and push web image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/web/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          build-args: |
            NEXT_PUBLIC_API_URL=http://localhost:8000
            NEXT_PUBLIC_SITE_URL=http://localhost:3000
            INTERNAL_API_URL=http://api:8000
          tags: |
            ghcr.io/vinoththecool7-netizen/kara-web:latest
            ghcr.io/vinoththecool7-netizen/kara-web:sha-${{ steps.sha.outputs.short }}
          cache-from: type=gha,scope=web
          cache-to: type=gha,mode=max,scope=web
```

- [ ] **Step 2: Validate YAML**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: publish multi-arch api/web images to GHCR on master"
```

---

### Task 2: Compose split — pull by default, build override, optional .env

**Files:**
- Modify: `docker-compose.yml` (api/web: `image:` instead of `build:`; env_file optional)
- Create: `docker-compose.build.yml`
- Modify: `docker-compose.test.yml` (add api build section)
- Modify: `scripts/smoke_test.sh` (drop `.env` copy; add build override file)

- [ ] **Step 1: In `docker-compose.yml`, replace the api service's `build:` block and env_file**

```yaml
  api:
    image: ghcr.io/vinoththecool7-netizen/kara-api:latest
    ports:
      # Loopback only by default — the API has no authentication, so binding
      # wider exposes every chat session to the whole network. The web UI
      # reaches it through the internal network (http://api:8000) regardless.
      # Set KARA_BIND_HOST=0.0.0.0 only behind your own auth/reverse proxy.
      - "${KARA_BIND_HOST:-127.0.0.1}:8000:8000"
    env_file:
      # Optional: without it Kara boots unconfigured and the web UI shows
      # the first-run setup wizard.
      - path: apps/api/.env
        required: false
    environment:
      - DATABASE_URL=postgresql+asyncpg://kara:${KARA_DB_PASSWORD:-kara}@db:5432/kara
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
```

- [ ] **Step 2: Replace the web service's `build:` block**

```yaml
  web:
    image: ghcr.io/vinoththecool7-netizen/kara-web:latest
    ports:
      # Loopback only by default: the UI proxies straight to the
      # unauthenticated API, so exposing it wider exposes all data too.
      - "${KARA_BIND_HOST:-127.0.0.1}:3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_SITE_URL=http://localhost:3000
      - INTERNAL_API_URL=http://api:8000
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:3000/', r => process.exit(r.statusCode===200?0:1)).on('error', () => process.exit(1))"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 15s
```

- [ ] **Step 3: Create `docker-compose.build.yml`**

```yaml
# Build-from-source override for contributors and custom deployments
# (e.g. non-localhost NEXT_PUBLIC_* values, which are baked at build time):
#   docker compose -f docker-compose.yml -f docker-compose.build.yml up --build
services:
  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8000
        NEXT_PUBLIC_SITE_URL: http://localhost:3000
        INTERNAL_API_URL: http://api:8000
```

- [ ] **Step 4: Add the api build section to `docker-compose.test.yml`** (smoke test must exercise the current checkout, not the published image)

```yaml
# Override for smoke testing — uses fake LLM provider (no API key needed)
# and builds the API from the current checkout instead of pulling GHCR.
services:
  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    environment:
      - LLM_PROVIDER=fake
```

- [ ] **Step 5: In `scripts/smoke_test.sh`, remove the `.env` bootstrap block** (lines 68-72: the `if [ ! -f "apps/api/.env" ]` block) — `.env` is now optional.

- [ ] **Step 6: Validate**

Run: `docker compose config -q && docker compose -f docker-compose.yml -f docker-compose.build.yml config -q && docker compose -f docker-compose.yml -f docker-compose.test.yml config -q && echo OK`
Expected: `OK` (no errors)

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml docker-compose.build.yml docker-compose.test.yml scripts/smoke_test.sh
git commit -m "compose: pull prebuilt GHCR images by default; build via override; .env optional"
```

---

### Task 3: Ollama opt-in profile

**Files:**
- Modify: `docker-compose.yml` (two services + volume)

- [ ] **Step 1: Add services under `profiles: ["local"]` and the volume**

```yaml
  # Fully-local LLM (opt-in): docker compose --profile local up -d
  # Pulls ${OLLAMA_MODEL:-llama3.1} on first start; the setup wizard
  # auto-detects it at http://ollama:11434.
  ollama:
    image: ollama/ollama:latest
    profiles: ["local"]
    volumes:
      - kara-ollama-data:/root/.ollama
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

  ollama-init:
    image: ollama/ollama:latest
    profiles: ["local"]
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      - OLLAMA_HOST=http://ollama:11434
    entrypoint: ["/bin/sh", "-c", "ollama pull ${OLLAMA_MODEL:-llama3.1}"]
    restart: "no"
```

And extend the volumes block:

```yaml
volumes:
  kara-db-data:
  kara-ollama-data:
```

- [ ] **Step 2: Validate**

Run: `docker compose --profile local config -q && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "compose: opt-in 'local' profile with Ollama + model auto-pull"
```

---

### Task 4: `runtime_settings` table (model + migration)

**Files:**
- Modify: `apps/api/src/kara_api/db/models.py` (append model)
- Create: `apps/api/alembic/versions/002_runtime_settings.py`
- Test: `apps/api/tests/test_db_models.py` (append)

- [ ] **Step 1: Write the failing test** (append to `apps/api/tests/test_db_models.py`, following its existing style)

```python
def test_runtime_setting_model_mapping():
    from kara_api.db.models import RuntimeSetting

    assert RuntimeSetting.__tablename__ == "runtime_settings"
    setting = RuntimeSetting(key="LLM_PROVIDER", value="openai")
    assert setting.key == "LLM_PROVIDER"
    assert setting.value == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_db_models.py::test_runtime_setting_model_mapping -q`
Expected: FAIL — `ImportError: cannot import name 'RuntimeSetting'`

- [ ] **Step 3: Append the model to `apps/api/src/kara_api/db/models.py`**

```python
# ---------------------------------------------------------------------------
# Runtime settings (first-run setup wizard)
# ---------------------------------------------------------------------------


class RuntimeSetting(Base):
    """Key/value config written by the setup wizard.

    Only consulted when the environment does not already configure an LLM
    (see kara_api.runtime_config.is_env_configured).
    """

    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Create `apps/api/alembic/versions/002_runtime_settings.py`**

```python
"""runtime_settings -- key/value store for the first-run setup wizard

Revision ID: 002
Revises: 001
Create Date: 2026-07-02

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
```

- [ ] **Step 5: Run tests**

Run: `cd apps/api && python -m pytest tests/test_db_models.py tests/test_migration.py -q`
Expected: PASS (migration tests may be integration-marked; deselected is fine)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/kara_api/db/models.py apps/api/alembic/versions/002_runtime_settings.py apps/api/tests/test_db_models.py
git commit -m "feat(api): runtime_settings table for wizard-managed config"
```

---

### Task 5: Runtime-config layer

**Files:**
- Create: `apps/api/src/kara_api/runtime_config.py`
- Test: `apps/api/tests/test_runtime_config.py`

- [ ] **Step 1: Write the failing tests** (`apps/api/tests/test_runtime_config.py`)

```python
"""Tests for the DB-backed runtime configuration layer."""

import pytest

from kara_api.config import Settings
from kara_api.runtime_config import (
    WIZARD_KEYS,
    apply_overrides,
    is_env_configured,
    mask_key,
)


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


class TestIsEnvConfigured:
    def test_default_settings_are_unconfigured(self):
        assert is_env_configured(_settings()) is False

    def test_api_key_locks_config_to_env(self):
        assert is_env_configured(_settings(LLM_API_KEY="sk-test")) is True

    def test_ollama_provider_locks_config_to_env(self):
        assert is_env_configured(_settings(LLM_PROVIDER="ollama")) is True

    def test_fake_provider_locks_config_to_env(self):
        assert is_env_configured(_settings(LLM_PROVIDER="fake")) is True


class TestMaskKey:
    def test_empty_key(self):
        assert mask_key("") == ""

    def test_long_key_shows_last_four(self):
        assert mask_key("sk-abcdefghijklmnop") == "••••mnop"

    def test_short_key_fully_masked(self):
        assert mask_key("short") == "••••"


class TestApplyOverrides:
    def test_overlays_wizard_keys(self):
        settings = _settings()
        out = apply_overrides(
            settings, {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "sk-ant-1234"}
        )
        assert out.LLM_PROVIDER == "anthropic"
        assert out.LLM_API_KEY == "sk-ant-1234"
        # untouched fields keep their values
        assert out.SESSION_TTL_DAYS == settings.SESSION_TTL_DAYS

    def test_ignores_non_wizard_keys(self):
        out = apply_overrides(_settings(), {"DATABASE_URL": "postgresql://evil"})
        assert "evil" not in out.DATABASE_URL

    def test_empty_overrides_returns_equivalent_settings(self):
        settings = _settings()
        assert apply_overrides(settings, {}) == settings


def test_wizard_keys_are_valid_settings_fields():
    for key in WIZARD_KEYS:
        assert key in Settings.model_fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_runtime_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kara_api.runtime_config'`

- [ ] **Step 3: Create `apps/api/src/kara_api/runtime_config.py`**

```python
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
    """Read wizard-written rows; empty dict when none (or table missing)."""
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
                .on_conflict_do_update(
                    index_elements=["key"], set_={"value": value}
                )
            )
            await session.execute(stmt)
        await session.commit()
```

- [ ] **Step 4: Run tests**

Run: `cd apps/api && python -m pytest tests/test_runtime_config.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/kara_api/runtime_config.py apps/api/tests/test_runtime_config.py
git commit -m "feat(api): runtime-config layer with env-over-DB precedence"
```

---

### Task 6: Setup router (status / test / save)

**Files:**
- Create: `apps/api/src/kara_api/routers/setup.py`
- Modify: `apps/api/src/kara_api/routers/__init__.py`
- Modify: `apps/api/src/kara_api/main.py` (include router)
- Test: `apps/api/tests/test_setup_endpoints.py`

- [ ] **Step 1: Write the failing tests** (`apps/api/tests/test_setup_endpoints.py`)

```python
"""Tests for the first-run setup wizard endpoints."""

import httpx
import pytest

from kara_api.config import get_settings
from kara_api.routers import setup as setup_module


@pytest.fixture(autouse=True)
def unconfigured_env(monkeypatch):
    """Simulate a fresh install: no key, default provider, no DB overrides.

    setenv("", …) rather than delenv: pydantic-settings also reads
    apps/api/.env, and only a real (even empty) env var overrides it.
    """
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()

    async def no_overrides() -> dict:
        return {}

    monkeypatch.setattr(setup_module, "get_runtime_overrides", no_overrides)

    async def no_ollama(settings) -> dict:
        return {"reachable": False, "base_url": "", "models": []}

    monkeypatch.setattr(setup_module, "_detect_ollama", no_ollama)
    yield
    get_settings.cache_clear()


async def test_status_unconfigured(client):
    resp = await client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["source"] is None
    assert body["api_key_masked"] == ""


async def test_status_env_locked(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-verylongtestkey9876")
    get_settings.cache_clear()
    resp = await client.get("/api/v1/setup/status")
    body = resp.json()
    assert body["configured"] is True
    assert body["source"] == "env"
    assert body["api_key_masked"] == "••••9876"
    assert "sk-verylongtestkey9876" not in resp.text


async def test_status_db_configured(client, monkeypatch):
    async def overrides() -> dict:
        return {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "sk-ant-key-4321"}

    monkeypatch.setattr(setup_module, "get_runtime_overrides", overrides)
    resp = await client.get("/api/v1/setup/status")
    body = resp.json()
    assert body["configured"] is True
    assert body["source"] == "db"
    assert body["provider"] == "anthropic"
    assert body["api_key_masked"] == "••••4321"


async def test_save_rejected_when_env_locked(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    get_settings.cache_clear()
    resp = await client.post(
        "/api/v1/setup", json={"provider": "openai", "api_key": "sk-x"}
    )
    assert resp.status_code == 409


async def test_save_validates_then_persists(client, monkeypatch):
    saved: dict = {}

    async def fake_save(values: dict) -> None:
        saved.update(values)

    async def ok_validate(provider, api_key, model, base_url, ollama_base_url):
        return True, "Connection OK."

    monkeypatch.setattr(setup_module, "save_runtime_config", fake_save)
    monkeypatch.setattr(setup_module, "_validate", ok_validate)

    resp = await client.post(
        "/api/v1/setup",
        json={"provider": "openai", "api_key": "sk-new-key-1234", "model": ""},
    )
    assert resp.status_code == 200
    assert saved["LLM_PROVIDER"] == "openai"
    assert saved["LLM_API_KEY"] == "sk-new-key-1234"
    assert saved["LLM_MODEL"] == "gpt-4o"  # default filled in
    # true-OpenAI setups also get embeddings configured
    assert saved["EMBEDDING_PROVIDER"] == "openai"
    assert "sk-new-key-1234" not in resp.text


async def test_save_rejects_invalid_credentials(client, monkeypatch):
    async def bad_validate(provider, api_key, model, base_url, ollama_base_url):
        return False, "Invalid API key."

    monkeypatch.setattr(setup_module, "_validate", bad_validate)
    resp = await client.post(
        "/api/v1/setup", json={"provider": "openai", "api_key": "sk-bad"}
    )
    assert resp.status_code == 400


async def test_test_endpoint_reports_result(client, monkeypatch):
    async def ok_validate(provider, api_key, model, base_url, ollama_base_url):
        return True, "Connection OK."

    monkeypatch.setattr(setup_module, "_validate", ok_validate)
    resp = await client.post(
        "/api/v1/setup/test", json={"provider": "openai", "api_key": "sk-x"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "message": "Connection OK."}


class TestValidate:
    """_validate against a mocked httpx transport."""

    def _client(self, handler) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def test_openai_valid(self):
        def handler(request):
            assert request.headers["Authorization"] == "Bearer sk-good"
            return httpx.Response(200, json={"data": []})

        ok, _ = await setup_module._validate(
            "openai", "sk-good", "gpt-4o", "", "", client=self._client(handler)
        )
        assert ok is True

    async def test_openai_bad_key(self):
        def handler(request):
            return httpx.Response(401, json={"error": "bad key"})

        ok, message = await setup_module._validate(
            "openai", "sk-bad", "gpt-4o", "", "", client=self._client(handler)
        )
        assert ok is False
        assert "key" in message.lower()

    async def test_ollama_reachable(self):
        def handler(request):
            return httpx.Response(200, json={"models": [{"name": "llama3.1:latest"}]})

        ok, _ = await setup_module._validate(
            "ollama", "", "llama3.1", "", "http://ollama:11434",
            client=self._client(handler),
        )
        assert ok is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_setup_endpoints.py -q`
Expected: FAIL — `ImportError` (no `kara_api.routers.setup`)

- [ ] **Step 3: Create `apps/api/src/kara_api/routers/setup.py`**

```python
"""First-run setup wizard endpoints.

Same trust model as the rest of the unauthenticated API: anyone who can
reach the instance can configure it, and the compose defaults bind to
loopback. API keys are accepted, validated, stored — never echoed back.
"""
from __future__ import annotations

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from kara_api.config import get_settings
from kara_api.runtime_config import (
    get_runtime_overrides,
    is_env_configured,
    mask_key,
    save_runtime_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])

PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.1",
}

# Where a compose-profile or host Ollama may live, tried in order after the
# configured OLLAMA_BASE_URL.
OLLAMA_CANDIDATE_URLS = (
    "http://ollama:11434",
    "http://host.docker.internal:11434",
)


class SetupRequest(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"]
    api_key: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    # OpenAI-compatible base URL (e.g. OpenRouter); empty = provider default.
    base_url: str = Field(default="", max_length=500)
    ollama_base_url: str = Field(default="", max_length=500)


class TestResult(BaseModel):
    ok: bool
    message: str


class OllamaStatus(BaseModel):
    reachable: bool
    base_url: str
    models: list[str]


class SetupStatus(BaseModel):
    configured: bool
    source: Literal["env", "db"] | None
    provider: str
    model: str
    api_key_masked: str
    ollama: OllamaStatus


async def _probe_ollama(
    base_url: str, client: httpx.AsyncClient | None = None
) -> list[str] | None:
    """Model names when an Ollama answers at base_url, else None."""
    if not base_url:
        return None
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=1.5)
    try:
        resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return None
    finally:
        if own_client:
            await client.aclose()


async def _detect_ollama(settings) -> dict:
    """Probe the configured URL, the compose profile, then the docker host."""
    seen: set[str] = set()
    for url in (settings.OLLAMA_BASE_URL, *OLLAMA_CANDIDATE_URLS):
        if not url or url in seen:
            continue
        seen.add(url)
        models = await _probe_ollama(url)
        if models is not None:
            return {"reachable": True, "base_url": url, "models": models}
    return {"reachable": False, "base_url": "", "models": []}


async def _validate(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    ollama_base_url: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, str]:
    """Cheap credential/reachability check; never sends chat content."""
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    try:
        if provider == "openai":
            base = (base_url or "https://api.openai.com/v1").rstrip("/")
            resp = await client.get(
                f"{base}/models", headers={"Authorization": f"Bearer {api_key}"}
            )
            if resp.status_code in (401, 403):
                return False, "Invalid API key."
            resp.raise_for_status()
            return True, "Connection OK."
        if provider == "anthropic":
            resp = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            if resp.status_code in (401, 403):
                return False, "Invalid API key."
            resp.raise_for_status()
            return True, "Connection OK."
        if provider == "ollama":
            models = await _probe_ollama(ollama_base_url, client=client)
            if models is None:
                return False, f"Ollama not reachable at {ollama_base_url}."
            if model and not any(
                m == model or m.startswith(f"{model}:") for m in models
            ):
                return (
                    True,
                    f"Connected, but model '{model}' is not pulled yet — "
                    f"run: ollama pull {model}",
                )
            return True, "Connection OK."
        return False, f"Unknown provider: {provider}"
    except httpx.HTTPStatusError as exc:
        return False, f"Provider returned HTTP {exc.response.status_code}."
    except Exception:
        logger.warning("Setup validation failed", exc_info=True)
        return False, "Could not reach the provider. Check the URL and network."
    finally:
        if own_client:
            await client.aclose()


def _derive_config(body: SetupRequest, default_ollama_url: str) -> dict[str, str]:
    """Turn a wizard submission into runtime_settings rows."""
    model = body.model or PROVIDER_DEFAULT_MODELS[body.provider]
    values: dict[str, str] = {
        "LLM_PROVIDER": body.provider,
        "LLM_API_KEY": body.api_key,
        "LLM_MODEL": model,
        "LLM_BASE_URL": body.base_url,
    }
    if body.provider == "openai" and not body.base_url:
        # True OpenAI key → it also works for embeddings (semantic search).
        values["EMBEDDING_PROVIDER"] = "openai"
        values["EMBEDDING_MODEL"] = "text-embedding-3-small"
    elif body.provider == "ollama":
        values["OLLAMA_BASE_URL"] = body.ollama_base_url or default_ollama_url
        values["EMBEDDING_PROVIDER"] = "ollama"
    # anthropic / OpenRouter: leave embedding config alone — search degrades
    # gracefully to keyword matching.
    return values


@router.get("/status", response_model=SetupStatus)
async def setup_status() -> SetupStatus:
    settings = get_settings()
    if is_env_configured(settings):
        return SetupStatus(
            configured=True,
            source="env",
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            api_key_masked=mask_key(settings.LLM_API_KEY),
            ollama=OllamaStatus(reachable=False, base_url="", models=[]),
        )

    overrides = await get_runtime_overrides()
    configured = bool(overrides.get("LLM_API_KEY")) or overrides.get(
        "LLM_PROVIDER"
    ) == "ollama"
    effective_provider = overrides.get("LLM_PROVIDER", settings.LLM_PROVIDER)
    effective_model = overrides.get("LLM_MODEL", settings.LLM_MODEL)
    # Ollama detection only matters while choosing a provider; skip the
    # probes (up to ~4.5s of timeouts) once configured.
    ollama = (
        {"reachable": False, "base_url": "", "models": []}
        if configured
        else await _detect_ollama(settings)
    )
    return SetupStatus(
        configured=configured,
        source="db" if configured else None,
        provider=effective_provider,
        model=effective_model,
        api_key_masked=mask_key(overrides.get("LLM_API_KEY", "")),
        ollama=OllamaStatus(**ollama),
    )


@router.post("/test", response_model=TestResult)
async def test_connection(body: SetupRequest) -> TestResult:
    settings = get_settings()
    ollama_url = body.ollama_base_url or settings.OLLAMA_BASE_URL
    model = body.model or PROVIDER_DEFAULT_MODELS[body.provider]
    ok, message = await _validate(
        body.provider, body.api_key, model, body.base_url, ollama_url
    )
    return TestResult(ok=ok, message=message)


@router.post("", response_model=SetupStatus)
async def save_setup(body: SetupRequest) -> SetupStatus:
    settings = get_settings()
    if is_env_configured(settings):
        raise HTTPException(
            status_code=409,
            detail="Configuration is managed via .env on this server.",
        )
    ollama_url = body.ollama_base_url or settings.OLLAMA_BASE_URL
    model = body.model or PROVIDER_DEFAULT_MODELS[body.provider]
    ok, message = await _validate(
        body.provider, body.api_key, model, body.base_url, ollama_url
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    values = _derive_config(body, default_ollama_url=ollama_url)
    await save_runtime_config(values)
    logger.info("Setup wizard configured provider=%s model=%s", body.provider, model)
    return SetupStatus(
        configured=True,
        source="db",
        provider=body.provider,
        model=model,
        api_key_masked=mask_key(body.api_key),
        ollama=OllamaStatus(reachable=False, base_url="", models=[]),
    )
```

- [ ] **Step 4: Register the router.** In `apps/api/src/kara_api/routers/__init__.py`:

```python
from kara_api.routers.chat import router as chat_router
from kara_api.routers.documents import router as documents_router
from kara_api.routers.knowledge import router as knowledge_router
from kara_api.routers.setup import router as setup_router
from kara_api.routers.tax import router as tax_router

__all__ = [
    "chat_router",
    "documents_router",
    "knowledge_router",
    "setup_router",
    "tax_router",
]
```

In `apps/api/src/kara_api/main.py`, extend the import and add after the other routers:

```python
from kara_api.routers import (
    chat_router,
    documents_router,
    knowledge_router,
    setup_router,
    tax_router,
)
...
    app.include_router(setup_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 5: Run tests**

Run: `cd apps/api && python -m pytest tests/test_setup_endpoints.py -q`
Expected: PASS

- [ ] **Step 6: Lint**

Run: `cd apps/api && ruff check src tests`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/kara_api/routers/setup.py apps/api/src/kara_api/routers/__init__.py apps/api/src/kara_api/main.py apps/api/tests/test_setup_endpoints.py
git commit -m "feat(api): /setup endpoints — status, connection test, save"
```

---

### Task 7: Wire effective settings into chat + knowledge

**Files:**
- Modify: `apps/api/src/kara_api/routers/chat.py:427,457` (both `settings = get_settings()` lines)
- Modify: `apps/api/src/kara_api/routers/knowledge.py`
- Test: `apps/api/tests/test_chat_endpoints.py` (append one test)

- [ ] **Step 1: Write the failing test** (append to `apps/api/tests/test_chat_endpoints.py`, using its existing fixtures/style — adapt fixture names after reading the file):

```python
async def test_chat_uses_effective_settings(client, monkeypatch):
    """Wizard-saved (DB) config must reach the provider factory."""
    from kara_api.config import get_settings
    from kara_api import runtime_config
    from kara_api.routers import chat as chat_module

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()

    async def overrides() -> dict:
        return {"LLM_PROVIDER": "fake"}

    monkeypatch.setattr(runtime_config, "get_runtime_overrides", overrides)

    seen: dict = {}
    real_create = chat_module._create_agent_loop

    def spy(settings):
        seen["provider"] = settings.LLM_PROVIDER
        return real_create(settings)

    monkeypatch.setattr(chat_module, "_create_agent_loop", spy)

    resp = await client.post(
        "/api/v1/chat",
        json={"message": "Hello"},
        headers={"Accept": "application/json"},
    )
    assert seen["provider"] == "fake"
    get_settings.cache_clear()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_chat_endpoints.py::test_chat_uses_effective_settings -q`
Expected: FAIL — `seen["provider"] == "openai"` (env default, overrides ignored)

- [ ] **Step 3: Switch chat endpoints to effective settings.** In `chat.py` add import `from kara_api.runtime_config import get_effective_settings`, then in BOTH `create_chat` and `continue_chat` replace:

```python
    settings = get_settings()
```

with:

```python
    settings = await get_effective_settings()
```

(Keep the `get_settings` import only if still used elsewhere in the file; remove if unused.)

- [ ] **Step 4: Switch knowledge search.** In `knowledge.py`, drop the `Depends(get_settings)` parameter and resolve inside:

```python
from kara_api.db.connection import get_db_session
from kara_api.knowledge.embeddings import get_embedding_provider
from kara_api.knowledge.search import SearchResult, hybrid_search
from kara_api.runtime_config import get_effective_settings

...

@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """Search the tax knowledge base using hybrid search."""
    settings = await get_effective_settings()
    provider = get_embedding_provider(settings)
    ...
```

- [ ] **Step 5: Run the API suite**

Run: `cd apps/api && python -m pytest -q`
Expected: PASS (integration tests deselected as usual)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/kara_api/routers/chat.py apps/api/src/kara_api/routers/knowledge.py apps/api/tests/test_chat_endpoints.py
git commit -m "feat(api): chat + knowledge use wizard-aware effective settings"
```

---

### Task 8: Web — API client additions

**Files:**
- Modify: `apps/web/src/lib/api.ts` (append)
- Modify: `apps/web/src/types/chat.ts` or colocate types in api.ts (follow file conventions)
- Test: `apps/web/src/lib/api.test.ts` (append)

**Before writing any web code:** per `apps/web/AGENTS.md`, read the relevant guides in `apps/web/node_modules/next/dist/docs/` (routing + client components) — this Next.js 16 differs from training data.

- [ ] **Step 1: Write failing tests** (append to `apps/web/src/lib/api.test.ts`, matching its existing fetch-mock style — adapt after reading the file):

```ts
describe("setup api", () => {
  it("getSetupStatus parses the status payload", async () => {
    const status = {
      configured: false,
      source: null,
      provider: "openai",
      model: "gpt-4o",
      api_key_masked: "",
      ollama: { reachable: false, base_url: "", models: [] },
    };
    mockFetchOnce(200, status); // use the file's existing mock helper
    await expect(getSetupStatus()).resolves.toEqual(status);
  });

  it("saveSetup POSTs the payload and returns status", async () => {
    const status = {
      configured: true,
      source: "db",
      provider: "openai",
      model: "gpt-4o",
      api_key_masked: "••••1234",
      ollama: { reachable: false, base_url: "", models: [] },
    };
    mockFetchOnce(200, status);
    await expect(
      saveSetup({ provider: "openai", api_key: "sk-x", model: "", base_url: "", ollama_base_url: "" }),
    ).resolves.toEqual(status);
  });

  it("saveSetup surfaces HTTP errors", async () => {
    mockFetchOnce(400, { detail: "Invalid API key." });
    await expect(
      saveSetup({ provider: "openai", api_key: "bad", model: "", base_url: "", ollama_base_url: "" }),
    ).rejects.toThrow(/Invalid API key/);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npx vitest run src/lib/api.test.ts`
Expected: FAIL — `getSetupStatus is not defined`

- [ ] **Step 3: Append to `apps/web/src/lib/api.ts`**

```ts
// ---------------------------------------------------------------------------
// Setup wizard
// ---------------------------------------------------------------------------

const SETUP_PREFIX = "/api/v1/setup";

export interface OllamaStatus {
  reachable: boolean;
  base_url: string;
  models: string[];
}

export interface SetupStatus {
  configured: boolean;
  source: "env" | "db" | null;
  provider: string;
  model: string;
  api_key_masked: string;
  ollama: OllamaStatus;
}

export interface SetupPayload {
  provider: "openai" | "anthropic" | "ollama";
  api_key: string;
  model: string;
  base_url: string;
  ollama_base_url: string;
}

export async function getSetupStatus(): Promise<SetupStatus> {
  const response = await fetchWithRetry(`${SETUP_PREFIX}/status`, {
    method: "GET",
    headers: buildJsonHeaders(),
  });
  await assertOk(response, "getSetupStatus");
  return response.json();
}

export async function testSetup(
  payload: SetupPayload,
): Promise<{ ok: boolean; message: string }> {
  const response = await fetchWithRetry(`${SETUP_PREFIX}/test`, {
    method: "POST",
    headers: buildJsonHeaders(),
    body: JSON.stringify(payload),
  });
  await assertOk(response, "testSetup");
  return response.json();
}

export async function saveSetup(payload: SetupPayload): Promise<SetupStatus> {
  const response = await fetchWithRetry(SETUP_PREFIX, {
    method: "POST",
    headers: buildJsonHeaders(),
    body: JSON.stringify(payload),
  });
  await assertOk(response, "saveSetup");
  return response.json();
}
```

- [ ] **Step 4: Run tests**

Run: `cd apps/web && npx vitest run src/lib/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts
git commit -m "feat(web): setup API client (status/test/save)"
```

---

### Task 9: Web — setup wizard page + chat guard

**Files:**
- Create: `apps/web/src/components/setup/SetupWizard.tsx`
- Create: `apps/web/src/components/setup/SetupWizard.spec.tsx`
- Create: `apps/web/src/app/setup/page.tsx`
- Modify: `apps/web/src/components/chat/ChatLayout.tsx` (redirect guard)

- [ ] **Step 1: Write failing component test** (`SetupWizard.spec.tsx`, matching `MessageBubble.spec.tsx` conventions — adapt imports/setup after reading it):

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { SetupWizard } from "./SetupWizard";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const unconfigured: api.SetupStatus = {
  configured: false,
  source: null,
  provider: "openai",
  model: "gpt-4o",
  api_key_masked: "",
  ollama: { reachable: false, base_url: "", models: [] },
};

describe("SetupWizard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getSetupStatus").mockResolvedValue(unconfigured);
  });

  it("renders provider choices", async () => {
    render(<SetupWizard />);
    expect(await screen.findByText(/OpenAI/)).toBeInTheDocument();
    expect(screen.getByText(/Anthropic/)).toBeInTheDocument();
    expect(screen.getByText(/OpenRouter/)).toBeInTheDocument();
    expect(screen.getByText(/Local \(Ollama\)/)).toBeInTheDocument();
  });

  it("hides the key field for Ollama and shows detected models", async () => {
    vi.spyOn(api, "getSetupStatus").mockResolvedValue({
      ...unconfigured,
      ollama: { reachable: true, base_url: "http://ollama:11434", models: ["llama3.1:latest"] },
    });
    render(<SetupWizard />);
    await userEvent.click(await screen.findByText(/Local \(Ollama\)/));
    expect(screen.queryByLabelText(/API key/i)).not.toBeInTheDocument();
    expect(screen.getByText(/llama3.1:latest/)).toBeInTheDocument();
  });

  it("tests the connection and reports the result", async () => {
    const test = vi
      .spyOn(api, "testSetup")
      .mockResolvedValue({ ok: true, message: "Connection OK." });
    render(<SetupWizard />);
    await userEvent.type(await screen.findByLabelText(/API key/i), "sk-test");
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));
    await waitFor(() => expect(test).toHaveBeenCalled());
    expect(await screen.findByText(/Connection OK/)).toBeInTheDocument();
  });

  it("saves and reports success", async () => {
    const save = vi.spyOn(api, "saveSetup").mockResolvedValue({
      ...unconfigured,
      configured: true,
      source: "db",
      api_key_masked: "••••1234",
    });
    render(<SetupWizard />);
    await userEvent.type(await screen.findByLabelText(/API key/i), "sk-test-1234");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(save).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npx vitest run src/components/setup/SetupWizard.spec.tsx`
Expected: FAIL — cannot resolve `./SetupWizard`

- [ ] **Step 3: Create `SetupWizard.tsx`** — client component, styled with the app's existing Tailwind idiom (inspect `ChatWindow.tsx`/`MessageInput.tsx` for class conventions and reuse them):

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  getSetupStatus,
  saveSetup,
  testSetup,
  type SetupPayload,
  type SetupStatus,
} from "@/lib/api";

type ProviderChoice = "openai" | "anthropic" | "openrouter" | "ollama";

const PROVIDER_LABELS: Record<ProviderChoice, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  openrouter: "OpenRouter",
  ollama: "Local (Ollama)",
};

const DEFAULT_MODELS: Record<ProviderChoice, string> = {
  openai: "gpt-4o",
  anthropic: "claude-sonnet-4-20250514",
  openrouter: "openai/gpt-4o",
  ollama: "llama3.1",
};

function toPayload(
  choice: ProviderChoice,
  apiKey: string,
  model: string,
  ollamaBaseUrl: string,
): SetupPayload {
  return {
    provider: choice === "openrouter" ? "openai" : choice,
    api_key: choice === "ollama" ? "" : apiKey,
    model: model || DEFAULT_MODELS[choice],
    base_url: choice === "openrouter" ? "https://openrouter.ai/api/v1" : "",
    ollama_base_url: choice === "ollama" ? ollamaBaseUrl : "",
  };
}

export function SetupWizard() {
  const router = useRouter();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [choice, setChoice] = useState<ProviderChoice>("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);
  const [busy, setBusy] = useState<"test" | "save" | null>(null);

  useEffect(() => {
    getSetupStatus()
      .then((s) => {
        setStatus(s);
        if (s.ollama.reachable) setChoice("ollama");
      })
      .catch(() => setStatus(null));
  }, []);

  const envLocked = status?.source === "env";
  const ollama = status?.ollama;

  const handleTest = async () => {
    setBusy("test");
    setFeedback(null);
    try {
      const result = await testSetup(
        toPayload(choice, apiKey, model, ollama?.base_url ?? ""),
      );
      setFeedback(result);
    } catch (err) {
      setFeedback({ ok: false, message: err instanceof Error ? err.message : "Request failed" });
    } finally {
      setBusy(null);
    }
  };

  const handleSave = async () => {
    setBusy("save");
    setFeedback(null);
    try {
      await saveSetup(toPayload(choice, apiKey, model, ollama?.base_url ?? ""));
      router.replace("/chat");
    } catch (err) {
      setFeedback({ ok: false, message: err instanceof Error ? err.message : "Save failed" });
    } finally {
      setBusy(null);
    }
  };

  if (envLocked) {
    return (
      <div className="mx-auto max-w-xl p-8 text-center">
        <h1 className="text-2xl font-semibold">Kara is configured via .env</h1>
        <p className="mt-2 text-slate-600">
          This server manages its LLM settings in <code>apps/api/.env</code>.
          Edit that file and restart to change providers.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Set up Kara</h1>
      <p className="mt-1 text-slate-600">
        Pick who runs the language model. Rupee math always runs locally in
        the deterministic tax engine — the LLM only converses.
      </p>

      <fieldset className="mt-6 grid grid-cols-2 gap-3">
        <legend className="sr-only">LLM provider</legend>
        {(Object.keys(PROVIDER_LABELS) as ProviderChoice[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => {
              setChoice(p);
              setModel("");
              setFeedback(null);
            }}
            aria-pressed={choice === p}
            className={`rounded-lg border p-3 text-left ${
              choice === p ? "border-blue-600 ring-1 ring-blue-600" : "border-slate-300"
            }`}
          >
            <span className="font-medium">{PROVIDER_LABELS[p]}</span>
            {p === "ollama" && (
              <span className="block text-xs text-slate-500">
                {ollama?.reachable ? "detected ✓" : "no local Ollama detected"}
              </span>
            )}
          </button>
        ))}
      </fieldset>

      {choice !== "ollama" ? (
        <label className="mt-6 block">
          <span className="text-sm font-medium">API key</span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={choice === "anthropic" ? "sk-ant-…" : "sk-…"}
            className="mt-1 w-full rounded-md border border-slate-300 p-2"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Stored on your server only; never shown again in full.
          </span>
        </label>
      ) : (
        <div className="mt-6">
          <span className="text-sm font-medium">Detected models</span>
          {ollama?.reachable && ollama.models.length > 0 ? (
            <ul className="mt-1 text-sm text-slate-700">
              {ollama.models.map((m) => (
                <li key={m}>
                  <button
                    type="button"
                    className={`underline-offset-2 ${model === m ? "font-semibold underline" : ""}`}
                    onClick={() => setModel(m)}
                  >
                    {m}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm text-slate-500">
              Start the local profile first:{" "}
              <code>docker compose --profile local up -d</code>
            </p>
          )}
        </div>
      )}

      <label className="mt-4 block">
        <span className="text-sm font-medium">Model</span>
        <input
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={DEFAULT_MODELS[choice]}
          className="mt-1 w-full rounded-md border border-slate-300 p-2"
        />
      </label>

      {feedback && (
        <p
          role="status"
          className={`mt-4 text-sm ${feedback.ok ? "text-emerald-700" : "text-red-600"}`}
        >
          {feedback.message}
        </p>
      )}

      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={handleTest}
          disabled={busy !== null}
          className="rounded-md border border-slate-300 px-4 py-2"
        >
          {busy === "test" ? "Testing…" : "Test connection"}
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={busy !== null}
          className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white"
        >
          {busy === "save" ? "Saving…" : "Save & start chatting"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `apps/web/src/app/setup/page.tsx`**

```tsx
import type { Metadata } from "next";
import { SetupWizard } from "@/components/setup/SetupWizard";

export const metadata: Metadata = {
  title: "Set up Kara",
  robots: { index: false },
};

export default function SetupPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SetupWizard />
    </div>
  );
}
```

- [ ] **Step 5: Add the guard to `ChatLayout.tsx`** — inside the component, alongside the existing hooks:

```tsx
import { useRouter } from "next/navigation";
import { getSetupStatus } from "@/lib/api";
...
  const router = useRouter();

  // First-run guard: an unconfigured backend can't chat — send the user to
  // the setup wizard instead of letting the first message fail.
  useEffect(() => {
    getSetupStatus()
      .then((s) => {
        if (!s.configured) router.replace("/setup");
      })
      .catch(() => {
        // API unreachable → the chat UI's own error handling covers it.
      });
  }, [router]);
```

- [ ] **Step 6: Run web tests + type-check + lint**

Run: `cd apps/web && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: all PASS/clean

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/setup apps/web/src/app/setup apps/web/src/components/chat/ChatLayout.tsx
git commit -m "feat(web): first-run setup wizard + chat redirect guard"
```

---

### Task 10: Documentation

**Files:**
- Modify: `README.md` (Quick start, Roadmap)
- Modify: `docs/self-hosting.md`
- Modify: `apps/api/.env.example` (header note)

- [ ] **Step 1: README Quick start** — replace the current Quick start code block + intro line with:

```markdown
All you need is Docker — configuration happens in your browser:

​```bash
git clone https://github.com/vinoththecool7-netizen/kara-ai.git
cd kara-ai
docker compose up -d          # pulls prebuilt images (~1 min)
​```

Open <http://localhost:3000> — a one-time setup screen asks for your LLM
provider (OpenAI, Anthropic, or OpenRouter key — or a fully local model).

**Fully local, no API key:** `docker compose --profile local up -d` also
starts [Ollama](https://ollama.com) and pulls `llama3.1`; the setup screen
detects it automatically. Your data never leaves your machine.

**Building from source** (contributors, custom domains):
`docker compose -f docker-compose.yml -f docker-compose.build.yml up --build`
```

- [ ] **Step 2: README Roadmap** — mark shipped items:

```markdown
- [x] Prebuilt Docker images (skip the build, `docker compose up` and go)
- [x] First-run setup in the UI (paste your API key in the browser, no `.env` editing)
```

- [ ] **Step 3: `docs/self-hosting.md`** — update "One-command setup" to the new flow (no `cp .env` step); reposition the env-vars table under a heading like "Advanced: configuring via .env" with a note that `.env` (when it sets a key or a keyless provider) takes precedence over and disables the wizard; update the Ollama section to lead with `docker compose --profile local up -d` (keeping the host-install alternative); add an "Upgrading" section:

```markdown
## Upgrading

​```bash
git pull                # refresh compose files & docs
docker compose pull     # fetch newer images
docker compose up -d
​```
```

- [ ] **Step 4: `apps/api/.env.example`** — add at the top:

```bash
# OPTIONAL — a fresh install no longer needs this file: the web UI shows a
# first-run setup wizard and stores config in the database. Use this file
# when you want config locked in the environment (it takes precedence over
# and disables the wizard).
```

- [ ] **Step 5: Commit**

```bash
git add README.md docs/self-hosting.md apps/api/.env.example
git commit -m "docs: zero-config quick start, local profile, upgrade notes"
```

---

### Task 11: Full verification

- [ ] **Step 1: API + engine suites**

Run: `source .venv/bin/activate && pytest packages/tax-engine/tests -q && (cd apps/api && python -m pytest -q && ruff check src tests)`
Expected: PASS, lint clean

- [ ] **Step 2: Web suite**

Run: `cd apps/web && npm test && npx tsc --noEmit && npm run lint`
Expected: PASS

- [ ] **Step 3: Compose configs**

Run: `docker compose config -q && docker compose --profile local config -q && docker compose -f docker-compose.yml -f docker-compose.build.yml config -q && docker compose -f docker-compose.yml -f docker-compose.test.yml config -q`
Expected: silent success

- [ ] **Step 4 (optional, if Docker is running locally): smoke test**

Run: `bash scripts/smoke_test.sh`
Expected: 3/3 passed (builds api from source via test override)

---

## Post-merge manual steps (owner)

1. Push to master → CI publishes `kara-api`/`kara-web` to GHCR.
2. In GitHub → Packages → each package → Package settings → **Change visibility → Public** (first publish defaults to private; pulls fail for users until this is done).
3. Re-verify a fresh-clone quick start on a clean machine: `git clone … && docker compose up -d`.
