# Self-hosting Kara

## Prerequisites

- Docker with Compose v2
- An LLM API key (OpenAI, Anthropic, or any OpenAI-compatible endpoint such
  as OpenRouter) — **or** a local [Ollama](https://ollama.com) install for a
  fully offline setup.

## One-command setup

```bash
git clone https://github.com/vinoththecool7-netizen/kara-ai.git
cd kara-ai
cp apps/api/.env.example apps/api/.env
# edit apps/api/.env: set LLM_API_KEY (and LLM_BASE_URL for OpenRouter)
docker compose up --build
```

- Web UI: <http://localhost:3000>
- API + OpenAPI docs: <http://localhost:8000/docs>

On first start the API runs migrations and seeds the 114-section tax-law
knowledge base automatically. If no embedding backend is reachable it seeds
without vectors and search degrades gracefully to keyword matching.

## Environment variables (`apps/api/.env`)

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
| `KARA_DB_PASSWORD` | `kara` | Shell env (not .env): Postgres password for compose |

## Fully local with Ollama (no API key)

```bash
ollama pull llama3.1
# in apps/api/.env:
#   LLM_PROVIDER=ollama
#   LLM_MODEL=llama3.1
#   OLLAMA_BASE_URL=http://host.docker.internal:11434
#   EMBEDDING_PROVIDER=ollama
docker compose up --build
```

Tool-calling quality depends on the model; llama3.1-8B works but a larger
model gives noticeably better results.

## Security model — read before exposing anything

Kara currently has **no authentication**: anyone who can reach the API can
read, create, and delete every chat session. It is designed for:

- personal use on `localhost`, or
- a private network / behind your own authenticating reverse proxy.

Do **not** put it on the public internet as-is. Built-in mitigations:
security headers, per-IP rate limiting, generic error messages, PAN
masking, session TTL, loopback-bound Postgres.

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
