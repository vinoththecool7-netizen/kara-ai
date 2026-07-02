<div align="center">

# Kara (कर)

**A private, self-hosted AI tax advisor for India — it computes, never guesses.**

[![CI](https://github.com/vinoththecool7-netizen/kara-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/vinoththecool7-netizen/kara-ai/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
[![Tax engine: MIT](https://img.shields.io/badge/tax--engine-MIT-green)](packages/tax-engine/LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Quick start](#quick-start) · [Why Kara](#why-kara) ·
[Self-hosting guide](docs/self-hosting.md) · [Contributing](CONTRIBUTING.md)

<!-- Hero demo: capture a 20–30s GIF of a chat session (question → streaming
     answer → tax breakdown card) and place it at docs/assets/demo.gif, then
     uncomment:
<img src="docs/assets/demo.gif" alt="Kara answering a tax question with a computed breakdown" width="800" />
-->

</div>

---

Your Form 16 is your PAN, your salary, and every investment you've made.
Right now your options for getting tax help with it are to upload it to a
filing portal's servers, or paste it into ChatGPT. Kara is the third
option: a tax advisor that runs on your own hardware. Documents are parsed
in memory and never written to disk, PANs are masked before anything is
stored, and with a local model the whole thing works offline — nothing
leaves your machine.

There's a second problem with asking ChatGPT, anyway: it is confidently
wrong about Indian tax arithmetic. Slab boundaries, the §87A rebate with
marginal relief, surcharge tiers — exactly the math language models fumble.
So in Kara, the language model is not allowed to do math. It converses,
asks clarifying questions, and calls tools; every rupee figure comes from a
deterministic rule engine with 950+ tests that anyone can audit.

```
You:   How much tax do I owe on a 15 lakh salary?
Kara:  Under the new regime for FY 2025-26, your tax is ₹97,500…
       [tax breakdown waterfall · old vs new regime comparison]
```

> [!IMPORTANT]
> Kara provides general tax information, not professional tax advice.
> Verify with a qualified professional before filing.

## Why Kara

**Your data stays yours.** ClearTax, Quicko, and every other filing portal
work by uploading your financial life to their servers. Kara is software
you run yourself. Bring your own LLM key (OpenAI, Anthropic, OpenRouter) —
or start it with one command in fully-local mode, where an on-device model
answers and no data ever touches the internet. Either way: documents parsed
in memory, PANs masked before storage, idle sessions deleted after 30 days.

**The numbers are computed, not generated.** The [tax
engine](packages/tax-engine/) covers FY 2025-26 slabs, every deduction cap,
capital gains across 7 asset classes, TDS rates, advance tax schedules,
§234A/B/C interest, and ITR form selection. The rules are plain YAML you
can read and check against the Income Tax Act; the engine is MIT-licensed,
so you can embed it in your own projects.

**It understands your documents.** Upload Form 16, AIS, or Form 26AS and
Kara fills in your profile and reconciles TDS across them. Then it answers
the questions calculator sites can't: *old regime or new, for me
specifically? Did my employer deduct the right TDS? What do I owe on my US
stock sales?*

**It shows its work.** Answers stream in with a tax-breakdown waterfall,
regime comparison, and deduction-gap cards — and explanations are grounded
in a 114-section knowledge base of the actual tax provisions, not vibes.

**What it doesn't do (yet):** file your ITR. Kara is for planning and
understanding; ITR JSON export for the e-filing portal is on the
[roadmap](#roadmap).

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
