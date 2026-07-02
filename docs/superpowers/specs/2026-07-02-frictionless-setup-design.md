# Frictionless setup: prebuilt images, first-run wizard, opt-in local Ollama

Date: 2026-07-02
Status: approved (user chose "wizard-first + opt-in Ollama")

## Goal

Cut first-run time from ~15–20 minutes to under 5, and remove every manual
file edit from the happy path. Three pieces:

1. **Prebuilt images on GHCR** — users pull compiled images instead of
   building Next.js + Python from source on their machine.
2. **First-run setup wizard** — `docker compose up -d` works with **no
   `.env` file at all**; the browser walks the user through provider choice,
   API key, and a connection test.
3. **Opt-in fully-local profile** — `docker compose --profile local up -d`
   adds an Ollama container and auto-pulls a model; the wizard detects it.

Explicitly rejected: always-on Ollama (forces a ~5 GB download on every
user, including those who immediately configure OpenAI).

## Part A — Prebuilt images (GHCR)

### CI publish job (`.github/workflows/ci.yml`)

New `publish` job:

- `needs: [tax-engine, api, web, smoke]` — publishes only when all tests pass.
- Runs only on `push` to `master` (not PRs).
- `permissions: { contents: read, packages: write }`.
- Logs into `ghcr.io` with `GITHUB_TOKEN`; uses buildx + QEMU for
  `linux/amd64,linux/arm64` (Indian dev laptops are heavily M-series).
- Pushes, for each of `apps/api/Dockerfile` and `apps/web/Dockerfile`
  (context `.`, web keeps its current default build args):
  - `ghcr.io/vinoththecool7-netizen/kara-api:latest` / `kara-web:latest`
  - `…:sha-<short-sha>` for pinning/rollback
- GitHub Actions layer cache (`cache-from/to: type=gha`).

Manual follow-up (owner, once): make both GHCR packages **public** in
GitHub package settings — first publish defaults to private.

### Compose split

- `docker-compose.yml` (end users): `api`/`web` switch from `build:` to
  `image: ghcr.io/…:latest`. `env_file` becomes
  `{path: apps/api/.env, required: false}` so a fresh clone boots with no
  `.env`. Everything else (loopback binds, healthchecks) unchanged.
- `docker-compose.build.yml` (new, contributors): re-adds the `build:`
  sections (including web build args). Usage:
  `docker compose -f docker-compose.yml -f docker-compose.build.yml up --build`.
- `docker-compose.test.yml`: additionally gets the api `build:` section so
  the smoke test builds the *current checkout* instead of pulling.
- `scripts/smoke_test.sh`: drop the `.env` copy step (no longer needed);
  compose invocation unchanged.

Known limitation (documented, accepted): the web image bakes
`NEXT_PUBLIC_*` values at build time with localhost defaults, so prebuilt
images serve the localhost use case; custom-domain deployments keep using
the build override.

## Part B — First-run setup wizard

### Config model

Two sources, strict precedence:

- **Env-configured** ("locked"): `LLM_API_KEY` non-empty **or**
  `LLM_PROVIDER` is `ollama`/`fake`. Env is the sole source of truth; the
  wizard is disabled and shows "managed via .env".
- Otherwise **DB-configured**: wizard writes rows to a new
  `runtime_settings` table; effective settings = env settings overlaid with
  DB rows. No rows → **unconfigured** → UI redirects to the wizard.

Wizard-managed keys: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`,
`LLM_BASE_URL`, `OLLAMA_BASE_URL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`.
Embedding settings are derived, not asked: openai → openai embeddings;
ollama → ollama embeddings; anthropic/openrouter → leave unreachable →
existing graceful keyword-search fallback.

### Backend

- Alembic migration `002`: `runtime_settings(key TEXT PK, value TEXT NOT
  NULL, updated_at timestamptz DEFAULT now())`.
- `kara_api/runtime_config.py`: `is_env_configured(settings)`,
  `get_effective_settings()` (async; overlays DB rows via
  `Settings.model_copy(update=…)`), `save_runtime_config(dict)`,
  `get_runtime_config()`.
- New router `routers/setup.py` under `/api/v1/setup`:
  - `GET /status` → `{configured, source: "env"|"db"|null, provider, model,
    api_key_masked, ollama: {reachable, base_url, models[]}}`. Ollama
    detection probes (≤1.5 s each): effective `OLLAMA_BASE_URL`,
    `http://ollama:11434` (compose profile), `http://host.docker.internal:11434`.
  - `POST /test` → cheap provider-specific credential check: openai-compat
    `GET {base}/models`; anthropic `GET /v1/models`; ollama `GET /api/tags`
    (+ model-present check). Returns `{ok, message}`; never echoes the key.
  - `POST /` (save) → `409` when env-configured; re-validates like `/test`;
    derives embedding keys; upserts; returns fresh status.
  - API keys are never returned in full anywhere — masked to last 4 chars.
- Wire-in: `chat.py` `create_chat`/`continue_chat` and `knowledge.py`
  search use `await get_effective_settings()` instead of `get_settings()`.
  Startup KB seeding keeps env settings (wizard can't have run yet on first
  boot; re-embedding after wizard setup is out of scope / roadmap).
- Security posture: same trust model as the rest of the unauthenticated
  API — anyone who can reach the instance can configure it; loopback-bound
  by default. No key material in logs or responses.

### Frontend (`apps/web`)

- New `/setup` page: provider choice (OpenAI / Anthropic / OpenRouter /
  Local Ollama) → key + model fields with per-provider defaults (OpenRouter
  pre-fills base URL; Ollama shows detected models instead of a key field) →
  **Test connection** → Save → redirect to chat.
- Chat page fetches `/setup/status` on load; unconfigured → redirect to
  `/setup`; env-locked or DB-configured → normal chat. `/setup` stays
  reachable later to change provider/key (when not env-locked).
- Per `apps/web/AGENTS.md`, consult the bundled Next.js docs before writing
  the page; follow existing component/test conventions (vitest + Testing
  Library).

### Tests

- API: runtime-config precedence (env-locked / DB overlay / unconfigured),
  status shape + masking, test-endpoint per provider (mocked httpx), save
  flow incl. 409 when env-locked.
- Web: wizard renders, provider switch changes fields, test+save flow with
  mocked fetch; chat redirect when unconfigured.

## Part C — Opt-in Ollama profile

In `docker-compose.yml`, both under `profiles: ["local"]`:

- `ollama`: `image: ollama/ollama`, volume `kara-ollama-data:/root/.ollama`,
  no published ports (compose-internal only), healthcheck `ollama list`.
- `ollama-init`: one-shot (`restart: "no"`), depends on `ollama` healthy,
  runs `ollama pull ${OLLAMA_MODEL:-llama3.1}` against `OLLAMA_HOST=http://ollama:11434`.

The wizard's detection (Part B) finds `http://ollama:11434` and preselects
"Local Ollama" with the pulled model listed. No env vars required.

## Documentation

- README: quick start becomes `git clone && docker compose up -d` → open
  browser → wizard (no `.env` edit); fully-local path via
  `--profile local`; contributor build override; tick the two shipped
  roadmap items.
- `docs/self-hosting.md`: same updates + "upgrading" (`docker compose
  pull`), `.env` repositioned as the advanced/locked-down path.
- `apps/api/.env.example`: header note that the file is optional now.

## Out of scope (follow-ups)

- Re-embedding the knowledge base after wizard-time embedding config.
- Authentication; hosted demo instance.
- Publishing versioned/semver image tags on releases.
