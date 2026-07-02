# Contributing to Kara

Thanks for helping make Indian tax computation open and auditable!

## Development setup (no Docker needed for tests)

```bash
git clone https://github.com/vinoththecool7-netizen/kara-ai.git
cd kara-ai
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e packages/tax-engine -e "apps/api[dev]"

# Backend tests (no database required — integration tests are opt-in)
pytest packages/tax-engine/tests
(cd apps/api && pytest)

# Frontend
cd apps/web && npm ci && npm test && npm run dev
```

For the full stack: `cp apps/api/.env.example apps/api/.env`, add an LLM
key, then `docker compose up --build`.

## Ground rules

1. **Tests first.** Every behavior change lands with a test that failed
   before the change. Tax-rule changes must cite the section of the
   Income-tax Act / Finance Act in the test docstring.
2. **Rules live in YAML.** Slabs, caps, rates, and thresholds belong in
   `packages/tax-engine/src/kara_tax_engine/rules/<fy>/` — never as Python
   literals. `tests/test_yaml_driven_caps.py` enforces this.
3. **Golden files are sacred.** If `tests/golden/expected.json` changes,
   your PR description must explain the tax-law reason. Regenerate with
   `python tests/golden/generate.py`.
4. **Lint clean.** `ruff check packages/tax-engine apps/api` and
   `npm run lint` / `npx tsc --noEmit` must pass (CI enforces this).
5. **Never commit secrets.** `.env` files are gitignored; keep it that way.
6. **Privacy.** PAN and similar identifiers must pass through
   `kara_api.privacy` helpers before being stored or returned.

## Pull requests

- One logical change per PR, with a description of *why*.
- CI must be green (lint, both Python suites, web build, Docker smoke test).
- For tax-content changes, link an authoritative source (Income Tax Dept
  circular, Finance Act text) in the PR.

## Good first issues

- Adding a financial year: see [docs/adding-new-fy.md](docs/adding-new-fy.md).
- Expanding the knowledge base: `apps/api/src/kara_api/data/tax_sections.yaml`.
- New TDS payment types: `rules/fy_2025_26/tds/rates.yaml`.
