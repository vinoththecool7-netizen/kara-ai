# Kara (कर) — Open-Source AI Tax Advisor for India

[![CI](https://github.com/vinoththecool7-netizen/kara-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/vinoththecool7-netizen/kara-ai/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Engine: MIT](https://img.shields.io/badge/tax--engine-MIT-green)](packages/tax-engine/LICENSE)

Chat with an AI tax advisor that **computes, never guesses**: every rupee
figure comes from a deterministic, YAML-rule-driven tax engine with 950+
tests — the LLM only orchestrates tools and explains results.

- **Conversational** — ask in plain English; Kara asks clarifying questions,
  streams answers token by token, and renders rich cards (tax breakdown
  waterfall, regime comparison, deduction gaps, capital gains).
- **Deterministic** — FY 2025-26 slabs, §87A rebate with marginal relief,
  surcharge tiers, every deduction cap, capital gains across 7 asset
  classes, TDS rates, advance tax schedules, §234A/B/C interest, and ITR
  form selection are all computed by code, driven by YAML rule files.
- **Document-aware** — upload Form 16, AIS, or Form 26AS (PDF/JSON) and
  Kara parses and auto-fills your profile, reconciling TDS across documents.
- **Private by design** — self-hosted, bring your own LLM key (OpenAI,
  Anthropic, OpenRouter, or fully local via Ollama). PANs are masked before
  storage; sessions expire automatically (30 days by default).

> **Disclaimer:** Kara provides general tax information, not professional
> tax advice. Verify with a qualified professional before filing.

## Quick start

```bash
git clone https://github.com/vinoththecool7-netizen/kara-ai.git
cd kara-ai
cp apps/api/.env.example apps/api/.env   # add your LLM API key
docker compose up --build
```

Open <http://localhost:3000> and ask *“How much tax do I owe on a 15 lakh
salary?”*. See [docs/self-hosting.md](docs/self-hosting.md) for the full
guide, including a no-API-key setup with Ollama.

## Architecture

```
apps/web        Next.js 16 chat UI (SSE streaming, rich cards)
apps/api        FastAPI agent backend
  ├─ agent      LLM loop, sessions, profile builder, advisory hints
  ├─ tools      12 function-calling tools the model may invoke
  ├─ parsers    Form 16 / AIS / 26AS PDF+JSON parsers
  └─ knowledge  114-section tax-law KB (pgvector + tsvector hybrid search)
packages/tax-engine   pip-installable deterministic rule engine
  └─ rules/fy_2025_26 slabs, deduction caps, capital gains, TDS — all YAML
```

The chat flow: user message → agent loop streams LLM turns → tool calls hit
the rule engine → results stream back as SSE events (`content_delta`,
`tool_result`, structured cards) → everything persists in PostgreSQL.

## Using the engine directly

```python
pip install kara-tax-engine   # or: pip install -e packages/tax-engine

from kara_tax_engine import TaxComputer
result = TaxComputer("2025-26").compute(gross_salary=1_500_000, regime="new")
print(result.total_tax_payable)  # 97500
```

## Configuration

All backend settings live in `apps/api/.env` — see
[apps/api/.env.example](apps/api/.env.example). Highlights:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | `openai` | Any OpenAI-compatible API (incl. OpenRouter), Anthropic, or Ollama |
| `EMBEDDING_PROVIDER` | `openai` | Semantic search; falls back to keyword search without it |
| `SESSION_TTL_DAYS` | `30` | Auto-delete idle sessions (0 disables) |
| `RATE_LIMIT_*` | on | Per-IP limits on chat/upload/compute |
| `KARA_DB_PASSWORD` | `kara` | Compose-level Postgres password |

## Development

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e packages/tax-engine -e "apps/api[dev]"
pytest packages/tax-engine/tests && (cd apps/api && pytest)
cd apps/web && npm ci && npm test && npm run dev
```

CI runs lint + the full test matrix + a Docker smoke test on every PR.
See [CONTRIBUTING.md](CONTRIBUTING.md), and
[docs/adding-new-fy.md](docs/adding-new-fy.md) for adding a financial year
(it's a YAML-only change).

## Deployment notes (single-host, self-hosted)

- No authentication is built in yet: the API trusts everyone who can reach
  it. **Run it on localhost or behind your own auth proxy** — do not expose
  it to the public internet as-is.
- Sessions are visible to anyone with access to the instance.

## License

- Platform (`apps/*`): [AGPL-3.0](LICENSE)
- Tax engine (`packages/tax-engine`): [MIT](packages/tax-engine/LICENSE)

Made with ❤️ in India.
