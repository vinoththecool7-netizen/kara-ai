# Self-hosting Kara

## Prerequisites

- Docker with Compose v2. That's it — an LLM API key (OpenAI, Anthropic, or
  any OpenAI-compatible endpoint such as OpenRouter) is entered in the
  browser on first run, or skipped entirely with the fully local profile.

## One-command setup

```bash
git clone https://github.com/vinoththecool7-netizen/kara-ai.git
cd kara-ai
docker compose up -d      # pulls prebuilt images from GHCR
```

- Web UI: <http://localhost:3000>
- API + OpenAPI docs: <http://localhost:8000/docs>

The web UI opens a **one-time setup screen**: pick a provider, paste your
key (or select a detected local Ollama), test the connection, save. Config
is stored in Kara's own PostgreSQL — no files to edit. Revisit
<http://localhost:3000/setup> any time to switch providers.

On first start the API runs migrations and seeds the 114-section tax-law
knowledge base automatically. If no embedding backend is reachable it seeds
without vectors and search degrades gracefully to keyword matching.

## Upgrading

```bash
git pull                # refresh compose files & docs
docker compose pull     # fetch newer images
docker compose up -d
```

## Building from source

Contributors — and deployments that need non-localhost `NEXT_PUBLIC_*`
values, which are baked into the web image at build time — use the build
override:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build
```

## Advanced: configuring via .env

`apps/api/.env` is **optional**. When it sets `LLM_API_KEY` (or a keyless
`LLM_PROVIDER` like `ollama`/`fake`), the environment becomes the sole
source of truth: the in-browser setup is disabled and wizard-saved values
are ignored. Use this for locked-down or scripted deployments. Copy
[.env.example](../apps/api/.env.example) to get started.

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` \| `anthropic` \| `ollama` \| `fake` |
| `LLM_API_KEY` | — | Not needed for `ollama`/`fake` |
| `LLM_MODEL` | `gpt-4o` | e.g. `claude-sonnet-4-20250514`, `llama3.1` |
| `LLM_BASE_URL` | — | Set `https://openrouter.ai/api/v1` for OpenRouter |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Use `http://host.docker.internal:11434` from Docker |
| `EMBEDDING_PROVIDER` | `openai` | `openai` \| `ollama` \| `fake`; optional |
| `SESSION_TTL_DAYS` | `30` | Idle sessions are deleted daily; `0` disables |
| `RATE_LIMIT_ENABLED` | `true` | Per-IP: 20/min chat, 10/min uploads, 60/min compute |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array |
| `ALLOWED_HOSTS` | `["localhost","127.0.0.1","api","test","testserver"]` | JSON array; Host-header allowlist — add your domain behind a proxy |
| `TRUST_PROXY_HEADERS` | `false` | Honour `X-Forwarded-For` for rate limits; enable only behind a trusted proxy |
| `KARA_BIND_HOST` | `127.0.0.1` | Shell env (not .env): address compose publishes ports on |
| `KARA_DB_PASSWORD` | `kara` | Shell env (not .env): Postgres password for compose |

## Fully local with Ollama (no API key)

```bash
docker compose --profile local up -d
```

This additionally starts an Ollama container and pulls
`${OLLAMA_MODEL:-llama3.1}` (~5 GB, one time) into a Docker volume. The
setup screen detects it at `http://ollama:11434` and preselects
"Local (Ollama)" — pick a model and save.

Already running Ollama on the host instead? Skip the profile; the setup
screen also probes `http://host.docker.internal:11434` and your configured
`OLLAMA_BASE_URL`.

Tool-calling quality depends on the model; llama3.1-8B works but a larger
model gives noticeably better results.

## Security model — read before exposing anything

Kara currently has **no authentication**: anyone who can reach the API can
read, create, and delete every chat session. It is designed for:

- personal use on `localhost`, or
- behind your own authenticating reverse proxy.

Do **not** put it on the public internet as-is. Built-in mitigations:
loopback-only port bindings, Host-header validation, security headers,
per-IP rate limiting, generic error messages, PAN masking (upload path and
LLM tool results), session TTL, loopback-bound Postgres.

### Exposing beyond localhost

By default `docker compose` publishes the web UI and API on `127.0.0.1`
only. To serve other devices, put an authenticating reverse proxy (Caddy,
nginx + basic auth, Tailscale, …) in front and:

1. `export KARA_BIND_HOST=0.0.0.0` **only if** the proxy runs on another
   host; if it runs on the same machine, keep the loopback binding and
   point the proxy at `127.0.0.1:3000`.
2. Add your domain to the API's Host allowlist in `apps/api/.env`, e.g.
   `ALLOWED_HOSTS=["localhost","127.0.0.1","api","kara.example.com"]`.
   Requests with any other `Host` header are rejected with 400 — this is
   what stops DNS-rebinding attacks against the unauthenticated API.
3. Set `TRUST_PROXY_HEADERS=true` so per-IP rate limits use the client IP
   from `X-Forwarded-For` (leave it `false` without a proxy: the header is
   client-spoofable).
4. Change the database password: `export KARA_DB_PASSWORD=<something-strong>`.

Also note: `DEBUG=true` echoes full SQL statements (including chat
content) into the logs — never enable it on a shared machine.

## Data retention

- Chat sessions, messages, tool results, and the (PAN-masked) profile are
  stored in PostgreSQL and deleted `SESSION_TTL_DAYS` after last activity.
- Uploaded documents are parsed in memory and never written to disk;
  only extracted (masked/sanitized) fields are stored.
- Whatever you send to your configured LLM provider is governed by that
  provider's retention policy — use Ollama if that matters to you.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/health` returns 503 | Database not ready/reachable — check `docker compose logs db` |
| "Knowledge base seeding failed" in logs | App still works; search is empty. Re-run `python scripts/seed_knowledge_base.py` inside the api container |
| Chat answers but `search_tax_law` finds nothing | Embeddings unreachable → keyword-only mode; set a working `EMBEDDING_PROVIDER` and force re-seed |
| 429 responses | Per-IP rate limit — tune `RATE_LIMIT_*` |
| Web can't reach API in Docker | Ensure `INTERNAL_API_URL=http://api:8000` (compose sets this) |
