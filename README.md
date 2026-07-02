<div align="center">

# Kara (कर)

**The open-source AI tax advisor for India — it computes, never guesses.**

Chat with an AI that understands Indian income tax, where every rupee figure
comes from a deterministic rule engine with 950+ tests — not from an LLM's
imagination.

[![CI](https://github.com/vinoththecool7-netizen/kara-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/vinoththecool7-netizen/kara-ai/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Tax engine: MIT](https://img.shields.io/badge/tax--engine-MIT-green)](packages/tax-engine/LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Quick start](#quick-start) · [Why Kara?](#why-kara) · [Features](#features) ·
[Self-hosting guide](docs/self-hosting.md) · [Contributing](CONTRIBUTING.md)

<!-- Hero demo: capture a 20–30s GIF of a chat session (question → streaming
     answer → tax breakdown card) and place it at docs/assets/demo.gif, then
     uncomment:
<img src="docs/assets/demo.gif" alt="Kara answering a tax question with a computed breakdown" width="800" />
-->

</div>

---

Ask ChatGPT how much tax you owe on a ₹15 lakh salary and you'll get a
confident answer that's frequently wrong — slab math, the §87A rebate,
marginal relief, and surcharge tiers are exactly the kind of arithmetic LLMs
fumble. Kara takes a different approach: **the LLM only converses and
orchestrates; a deterministic, YAML-rule-driven engine does every
calculation.** Same natural conversation, zero hallucinated numbers.

```
You:   How much tax do I owe on a 15 lakh salary?
Kara:  Under the new regime for FY 2025-26, your tax is ₹97,500…
       [tax breakdown waterfall · old vs new regime comparison]
```

> [!IMPORTANT]
> Kara provides general tax information, not professional tax advice.
> Verify with a qualified professional before filing.

## Why Kara?

|  | **Kara** | ChatGPT / Claude | ClearTax / Quicko | Calculator sites |
|---|---|---|---|---|
| Numbers are computed, not generated | ✅ deterministic engine | ❌ hallucinates | ✅ | ✅ |
| Conversational — ask anything, in plain English | ✅ | ✅ | ⚠️ limited chatbot | ❌ forms only |
| Reads your Form 16 / AIS / 26AS | ✅ | ⚠️ unreliable | ✅ | ❌ |
| Your PAN & salary stay on your machine | ✅ self-hosted | ❌ | ❌ | ⚠️ |
| Works fully offline (Ollama) | ✅ | ❌ | ❌ | ❌ |
| Free and open source | ✅ AGPL + MIT engine | ❌ | ❌ | ⚠️ closed |
| Files your ITR | 🔜 roadmap | ❌ | ✅ | ❌ |

## Features

- 💬 **Conversational** — ask in plain English; Kara asks clarifying
  questions, streams answers token by token, and renders rich cards: tax
  breakdown waterfall, old-vs-new regime comparison, deduction gap analysis,
  capital gains summaries.
- 🎯 **Deterministic** — FY 2025-26 slabs, §87A rebate with marginal relief,
  surcharge tiers, every deduction cap, capital gains across 7 asset classes,
  TDS rates, advance tax schedules, §234A/B/C interest, and ITR form
  selection — all computed by code, driven by [YAML rule
  files](packages/tax-engine/) anyone can audit.
- 📄 **Document-aware** — upload Form 16, AIS, or Form 26AS (PDF/JSON); Kara
  parses them, auto-fills your profile, and reconciles TDS across documents.
  Documents are parsed in memory and never written to disk.
- 📚 **Cites the law** — a 114-section tax-law knowledge base (hybrid
  pgvector + full-text search) grounds explanations in the actual provisions.
- 🔒 **Private by design** — self-hosted, bring your own LLM key (OpenAI,
  Anthropic, OpenRouter, or fully local via Ollama). PANs are masked before
  storage; idle sessions auto-delete after 30 days.

## Quick start

All you need is Docker — configuration happens in your browser:

```bash
git clone https://github.com/vinoththecool7-netizen/kara-ai.git
cd kara-ai
docker compose up -d      # pulls prebuilt images — no compile step
```

Open <http://localhost:3000> — a one-time setup screen asks for your LLM
provider (an OpenAI, Anthropic, or OpenRouter key — or a fully local model,
no key at all).

**Fully local, no API key:** `docker compose --profile local up -d` also
starts [Ollama](https://ollama.com) and pulls `llama3.1` (~5 GB, one time);
the setup screen detects it automatically. Your data never leaves your
machine.

Then try:

- *"How much tax do I owe on a 15 lakh salary?"*
- *"Old regime or new regime for me? I have a home loan and 80C investments."*
- *"Here's my Form 16 — did my employer deduct the right TDS?"* (attach the PDF)
- *"I sold some US stocks and mutual funds this year. What do I owe?"*

The full [self-hosting guide](docs/self-hosting.md) covers provider
details, upgrading, locking configuration via `.env`, and troubleshooting.
Contributors (or custom-domain deployments) build from source with
`docker compose -f docker-compose.yml -f docker-compose.build.yml up --build`.

## Architecture

```
apps/web              Next.js chat UI (SSE streaming, rich result cards)
apps/api              FastAPI agent backend
  ├─ agent            LLM loop, sessions, profile builder, advisory hints
  ├─ tools            12 function-calling tools the model may invoke
  ├─ parsers          Form 16 / AIS / 26AS PDF+JSON parsers
  └─ knowledge        114-section tax-law KB (pgvector + tsvector hybrid search)
packages/tax-engine   Deterministic rule engine (MIT-licensed, standalone)
  └─ rules/fy_2025_26 Slabs, deduction caps, capital gains, TDS — all YAML
```

User message → agent loop streams LLM turns → tool calls hit the rule
engine → results stream back as SSE events (`content_delta`, `tool_result`,
structured cards) → everything persists in PostgreSQL.

**The LLM never does arithmetic.** It decides *which* tool to call; the
engine returns exact figures; the LLM explains them.

## Use the tax engine without the chat

The engine is a standalone, MIT-licensed Python package — embed Indian tax
math in your own app:

```python
pip install -e packages/tax-engine   # PyPI release coming soon

from kara_tax_engine import TaxComputer
result = TaxComputer("2025-26").compute(gross_salary=1_500_000, regime="new")
print(result.total_tax_payable)  # 97500
```

New financial year? It's a YAML-only change — see
[docs/adding-new-fy.md](docs/adding-new-fy.md).

## Configuration

LLM provider/key/model are set in the browser on first run. Everything can
also be locked down in `apps/api/.env` — when that file sets a key (or a
keyless provider), it takes precedence and disables the in-browser setup
([full reference](docs/self-hosting.md#advanced-configuring-via-env)):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | `openai` | Any OpenAI-compatible API (incl. OpenRouter), Anthropic, or Ollama |
| `EMBEDDING_PROVIDER` | `openai` | Semantic search; degrades gracefully to keyword search |
| `SESSION_TTL_DAYS` | `30` | Auto-delete idle sessions (`0` disables) |
| `RATE_LIMIT_*` | on | Per-IP limits on chat/upload/compute |
| `ALLOWED_HOSTS` | localhost + internal | Host-header allowlist (anti DNS-rebinding); add your domain behind a proxy |
| `TRUST_PROXY_HEADERS` | `false` | Honour `X-Forwarded-For` for rate limits (only behind a trusted proxy) |
| `KARA_BIND_HOST` | `127.0.0.1` | Compose-level publish address; `0.0.0.0` only behind your own auth proxy |
| `KARA_DB_PASSWORD` | `kara` | Compose-level Postgres password |

## Security model

Kara has **no built-in authentication yet**: it is a single-user app for
`localhost` (or behind your own auth proxy) — do not expose it to the public
internet or a shared network as-is. The compose file therefore binds all
published ports to `127.0.0.1` by default; override with `KARA_BIND_HOST`
only when your own auth layer sits in front.
Mitigations in place: loopback-only defaults, Host-header validation
(anti DNS-rebinding), security headers, per-IP rate limits, PAN masking
(including inside LLM tool results), session TTL, loopback-bound Postgres,
generic error messages. Details in the
[self-hosting guide](docs/self-hosting.md#security-model--read-before-exposing-anything),
and see [SECURITY.md](SECURITY.md) for how to report vulnerabilities.

## Roadmap

- [x] Prebuilt Docker images (skip the build, `docker compose up` and go)
- [x] First-run setup in the UI (paste your API key in the browser, no `.env` editing)
- [ ] Built-in authentication (share an instance safely)
- [ ] FY 2026-27 rules (current-year advance tax planning)
- [ ] ITR JSON export for the income-tax e-filing portal
- [ ] `kara-tax-engine` on PyPI
- [ ] More documents: bank interest certificates, broker capital-gains statements

Have an opinion on priorities? [Open an issue](https://github.com/vinoththecool7-netizen/kara-ai/issues).

## Contributing

Contributions are welcome — and you don't need to know the codebase to make
a real one: **tax rules live in YAML**, so fixing a cap or adding a
provision is a data change with tests, not a code dive. Start with
[CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e packages/tax-engine -e "apps/api[dev]"
pytest packages/tax-engine/tests && (cd apps/api && pytest)
cd apps/web && npm ci && npm test && npm run dev
```

CI runs lint, the full test matrix (950+ engine tests), and a Docker smoke
test on every PR.

## License

- Platform (`apps/*`): [AGPL-3.0](LICENSE)
- Tax engine (`packages/tax-engine`): [MIT](packages/tax-engine/LICENSE) —
  use it in anything, including commercial products.

---

<div align="center">

Made with ❤️ in India · कर means "tax" in Hindi

</div>
