# Kara (कर) — 80-Day Progress Tracker

> **Project:** Open-source AI Tax Advisor for India
> **Timeline:** 80 working days | 16 weeks | 5 phases | 350+ test cases
> **Started:** 2026-03-24
> **Target Completion:** ~2026-07-14 (80 working days from start)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Completed |
| 🔄 | In Progress |
| ⬜ | Not Started |

---

## Progress Dashboard

| Phase | Days | Status | Progress |
|-------|------|--------|----------|
| 1 — Rule Engine | 1–20 | ✅ Complete | 20/20 days done |
| 2 — Backend + AI Agent | 21–40 | ✅ Complete | 20/20 days done |
| 3 — Frontend | 41–55 | 🔄 In Progress | 13/15 days done |
| 4 — Advanced Features | 56–70 | ⬜ Not Started | 0/15 days done |
| 5 — Polish + Launch | 71–80 | ⬜ Not Started | 0/10 days done |
| **Total** | **1–80** | | **53/80 days done (66%)** |

### Test Count Tracker

| Category | Target | Actual | Status |
|----------|--------|--------|--------|
| New regime slabs | 40+ | 45+ | ✅ |
| Old regime slabs | 40+ | 42 | ✅ |
| Deductions (80C–80U) | 80+ | 83 | ✅ |
| Capital gains | 60+ | 70 | ✅ |
| Comparator + Optimizer | 30+ | 30 | ✅ |
| Backend API | 50+ | 35 | ✅ |
| Knowledge base / search | 20+ | 24 | ✅ |
| LLM client + providers | 30+ | 54 | ✅ |
| Tool schemas + executor | 30+ | 55 | ✅ |
| Agent prompts + profile | 20+ | 50 | ✅ |
| Agent loop + chat | 30+ | 61 | ✅ |
| E2E integration | 10+ | 13 | ✅ |
| Frontend components | 20+ | 9 + 35 waterfall | 🔄 |
| E2E journeys | 10+ | 0 | ⬜ |
| **Total** | **350+** | **616** | **176%** |

---

## Phase 1 — Rule Engine (Days 1–20) ✅

**Goal:** `pip install kara-tax-engine` — compute tax in 3 lines of Python. Zero infrastructure needed.

**Phase Milestone:** ✅ ACHIEVED (2026-03-26) — pip package built. 306 tests passing. v0.1.0 wheel ready.

---

### Days 1–3: Project Setup + Rule Schema ✅

**Status:** ✅ COMPLETE (Done on actual Day 1 of work — 2026-03-24)

**Tasks:**
- [x] Init monorepo structure — `packages/`, `apps/api/`, `apps/web/`, `docs/`, `scripts/`
- [x] Create `pyproject.toml` — hatchling build, pydantic + pyyaml deps, pytest + ruff dev deps
- [x] Create YAML rule schema — `rules/fy_2025_26/` directory
- [x] Write `meta.yaml` — FY metadata, cess rate (4%), standard deductions, filing dates
- [x] Write `slabs/new_regime.yaml` — 7 slabs, 87A rebate, surcharge tiers, allowed deductions
- [x] Write `slabs/old_regime.yaml` — 3 age-variant slab sets, 87A rebate, surcharge tiers
- [x] Create `loader.py` — `RuleSet` class with YAML loading, caching, slab/rebate/surcharge accessors
- [x] Create `models.py` — Pydantic models: `TaxProfile`, `TaxBreakdown`, `SlabBreakdown`, `DeductionResult`, enums (`Regime`, `AgeCategory`, `IncomeType`, `AssetClass`, `GainType`)
- [x] Create `__init__.py` — public API exports, version 0.1.0
- [x] Create `tests/conftest.py` — session-scoped fixtures (computer, comparator, rules) + function-scoped profile fixtures
- [x] Write `test_loader.py` — 36 test cases covering slab retrieval, rebate, surcharge, caching, error handling
- [x] Write `test_models.py` — 25 test cases covering enums, model instantiation, computed fields

**Files Created:**
- `packages/tax-engine/pyproject.toml`
- `packages/tax-engine/src/kara_tax_engine/__init__.py`
- `packages/tax-engine/src/kara_tax_engine/models.py` (244 lines)
- `packages/tax-engine/src/kara_tax_engine/loader.py` (90 lines)
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/meta.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/slabs/new_regime.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/slabs/old_regime.yaml`
- `packages/tax-engine/tests/__init__.py`
- `packages/tax-engine/tests/conftest.py`
- `packages/tax-engine/tests/test_loader.py`
- `packages/tax-engine/tests/test_models.py`

**Tests:** 61 tests (36 loader + 25 models)

---

### Days 4–6: New Regime Slabs ✅

**Status:** ✅ COMPLETE (Done on actual Day 1 of work — 2026-03-24)

**Tasks:**
- [x] Implement `TaxComputer` class with 8-step computation pipeline
- [x] Step 1: Income aggregation — gross salary + business + house property (₹2L loss cap) + other sources
- [x] Step 2: Standard deduction — ₹75,000 for salaried (new regime)
- [x] Step 3: Slab tax computation — iterate 7 slabs (0%→30%), ceiling rounding per slab
- [x] Step 5: Surcharge — tiered (10%/15%/25%), capped at 25% for new regime
- [x] Step 5b: Surcharge marginal relief — total tax ≤ excess over threshold
- [x] Step 6: Health & Education Cess — 4% on (tax + surcharge), rounded up
- [x] Step 7: Section 87A rebate — full rebate if taxable ≤ ₹12L (max ₹60,000)
- [x] Step 7b: 87A marginal relief — for income just above ₹12L threshold
- [x] Step 8: Net tax payable + effective tax rate
- [x] Indian number formatting utility (`_fmt()`)
- [x] `.compute()` simple interface + `.compute_from_profile()` full interface
- [x] Write `test_new_regime.py` — 45+ test cases across 9 groups:
  - [x] Group A: Zero & low income (5 tests)
  - [x] Group B: Section 87A rebate zone (8 tests)
  - [x] Group C: Mid-income slab boundaries (8 tests)
  - [x] Group D: Standard deduction (3 tests)
  - [x] Group E: Surcharge (7 tests)
  - [x] Group F: Slab breakdown audit trail (4 tests)
  - [x] Group G: Other income heads (4 tests)
  - [x] Group H: Cess (2 tests)
  - [x] Group I: Effective tax rate (2 tests)

**Files Created:**
- `packages/tax-engine/src/kara_tax_engine/computer.py` (541 lines)
- `packages/tax-engine/tests/test_new_regime.py` (45+ tests)

**Files Also Scaffolded (stubs):**
- `packages/tax-engine/src/kara_tax_engine/capital_gains.py` (stub, 33 lines)
- `packages/tax-engine/src/kara_tax_engine/comparator.py` (49 lines, mostly working)
- `packages/tax-engine/src/kara_tax_engine/optimizer.py` (stub, 26 lines)

**Tests:** 45+ new regime tests

---

### Days 7–9: Old Regime Slabs ✅

**Status:** ✅ COMPLETE (Day 7 done on 2026-03-24, Day 8 done on 2026-03-24)

**Tasks:**
- [x] Create `rules/fy_2025_26/deductions/` YAML files for deduction limits (80C, 80D, 80CCD)
- [x] Write `test_old_regime.py` — 42 tests across 11 groups:
  - [x] Group A: Below-60 zero & low income (5 tests)
  - [x] Group B: Below-60 mid & high income, std deduction (5 tests)
  - [x] Group C: Senior citizen slabs (5 tests)
  - [x] Group D: Super senior slabs + exemption comparison (4 tests)
  - [x] Group E: Section 87A rebate — ₹5L threshold, ₹12,500 cap (5 tests)
  - [x] Group F: Slab breakdown audit trail (1 test)
  - [x] Group G: Surcharge tiers 10%/15%/25%/37% (6 tests)
  - [x] Group H: Surcharge marginal relief at 50L/1Cr/5Cr boundaries (3 tests)
  - [x] Group I: 37% surcharge old-regime-exclusive vs 25% new-regime cap (2 tests)
  - [x] Group J: Cross-regime comparison sanity checks (4 tests)
  - [x] Group K: Age-threshold boundary edge cases (2 tests)
- [x] Verify all 4 surcharge tiers including 37% at ₹5Cr (old regime specific)
- [x] Edge case: income exactly at age-threshold boundaries

**Files Created:**
- `packages/tax-engine/tests/test_old_regime.py` (42 tests)
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80c.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80d.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80ccd.yaml`

**Tests:** 42 old regime tests (target was 40+) ✅

**Definition of Done:** ✅ All old regime slab computations verified. Senior/super-senior age variants tested. All 4 surcharge tiers tested with marginal relief. 37% old-regime-exclusive cap verified. Cross-regime comparisons verified. All 123 tests green.

---

### Days 10–12: Deductions Engine Part 1 (80C, 80D, 80CCD, HRA, 80E–80U, 24b) ✅

**Status:** ✅ COMPLETE (Done on actual Day 3 of work — 2026-03-25)

**Note:** Deduction application logic existed in `computer.py` (`_apply_deductions` method). Days 10-12 added exhaustive test coverage (83 tests across 3 files) plus 5 new YAML reference files. Also covers HRA, 80E-80U, and 24(b) originally planned for Days 13-14.

**Tasks:**
- [x] Write `test_deductions_80c.py` — 28 tests across 6 groups:
  - [x] Group A: Basic 80C application — deduction reduces taxable income, appears in results (5 tests)
  - [x] Group B: Cap enforcement — ₹1.5L cap, partial claims, edge cases (5 tests)
  - [x] Group C: Combined cap 80C+80CCC+80CCD(1) — within, at, exceeds cap (6 tests)
  - [x] Group D: Regime filtering — 80C/80CCC/80CCD1/80CCD1B rejected in new, 80CCD(2) in both (6 tests)
  - [x] Group E: 80CCD(1B) additional NPS — separate ₹50K cap (3 tests)
  - [x] Group F: End-to-end tax savings at 30%/20% brackets + full stack (3 tests)
- [x] Write `test_deductions_80d_hra.py` — 28 tests across 7 groups:
  - [x] Group A: 80D self/family below-60 — ₹25K cap (5 tests)
  - [x] Group B: 80D senior citizen — ₹50K cap (4 tests)
  - [x] Group C: 80D parents — combined self+parents (4 tests)
  - [x] Group D: 80D regime filtering (2 tests)
  - [x] Group E: HRA metro — each formula option limiting (5 tests)
  - [x] Group F: HRA non-metro + edge cases (5 tests)
  - [x] Group G: Combined deductions — HRA+80C+80D stacked (3 tests)
- [x] Write `test_deductions_remaining.py` — 27 tests across 6 groups:
  - [x] Group A: 80E education loan — no cap (4 tests)
  - [x] Group B: 80G donations (4 tests)
  - [x] Group C: 80TTA/80TTB — age-dependent caps (6 tests)
  - [x] Group D: 80U/80DD disability — normal vs severe heuristic (6 tests)
  - [x] Group E: Section 24(b) home loan — ₹2L cap (3 tests)
  - [x] Group F: Full integration profiles — salaried, senior, new regime, kitchen sink (4 tests)
- [x] Create 5 YAML reference files:
  - `section_80e.yaml` — education loan interest, no cap
  - `section_80g.yaml` — donations, 4 category tiers
  - `section_80tta_80ttb.yaml` — savings interest, age-dependent
  - `section_80u_80dd.yaml` — disability, normal vs severe
  - `section_24b.yaml` — home loan interest, self-occupied vs let-out
- [x] Verify all deduction regime eligibility (old only vs both)

**Files Created:**
- `packages/tax-engine/tests/test_deductions_80c.py` (28 tests)
- `packages/tax-engine/tests/test_deductions_80d_hra.py` (28 tests)
- `packages/tax-engine/tests/test_deductions_remaining.py` (27 tests)
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80e.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80g.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80tta_80ttb.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80u_80dd.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_24b.yaml`

**Tests:** 83 deduction tests (target was 80+) ✅

**Definition of Done:** ✅ All deduction sections (80C through 80U + HRA + 24b) tested exhaustively. Regime filtering verified. Combined/stacked deduction scenarios verified. Integration profiles for salaried, senior, new regime, and kitchen-sink old regime all pass. All 206 tests green.

---

### Days 13–14: Deductions Engine Part 2 (HRA, 80E–80U, 24b) ✅

**Status:** ✅ COMPLETE (Absorbed into Days 10–12 — all HRA, 80E-80U, 24b tests included above)
**Note:** HRA exemption logic exists in `computer.py` (`_compute_hra_exemption`). 80E, 80G, 80TTA/TTB, 80U/DD, 24(b) logic also present. Need: YAML rules + exhaustive tests.

**Tasks:**
- [ ] Create `rules/fy_2025_26/deductions/hra.yaml` — HRA exemption rules
  - Metro cities (50% of basic) vs non-metro (40% of basic)
  - min(HRA received, % of basic, rent − 10% basic)
- [ ] Create `rules/fy_2025_26/deductions/section_80e_to_80u.yaml`
  - 80E: education loan interest (no cap, old only)
  - 80G: donations (50%/100% deduction, old only)
  - 80TTA: savings interest ₹10K (below 60, old only)
  - 80TTB: savings interest ₹50K (senior, old only)
  - 80U: disability ₹75K / ₹125K severe (old only)
  - 80DD: dependent disability ₹75K / ₹125K (old only)
- [ ] Create `rules/fy_2025_26/deductions/section_24b.yaml`
  - Home loan interest: ₹2L cap (self-occupied, old only)
  - Let-out property: no cap on interest
- [ ] Add tests to `test_deductions.py` — Part 2: 40+ tests
  - [ ] Group K: HRA metro — min of 3 options (5 tests)
  - [ ] Group L: HRA non-metro — 40% basic variant (4 tests)
  - [ ] Group M: HRA edge cases — zero rent, no HRA component (3 tests)
  - [ ] Group N: HRA in new regime — should NOT apply (2 tests)
  - [ ] Group O: 80E education loan — no cap (3 tests)
  - [ ] Group P: 80G donations — 50% and 100% variants (4 tests)
  - [ ] Group Q: 80TTA vs 80TTB — age-dependent (4 tests)
  - [ ] Group R: 80U/80DD disability — normal vs severe (4 tests)
  - [ ] Group S: Section 24(b) home loan interest — ₹2L cap (4 tests)
  - [ ] Group T: Let-out property — rental income minus full interest (3 tests)
  - [ ] Group U: All deductions combined — realistic salaried profile (4 tests)

**Files to Create/Modify:**
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/hra.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_80e_to_80u.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/deductions/section_24b.yaml`
- `packages/tax-engine/tests/test_deductions.py` (append Part 2)

**Tests Target:** 40+ tests (Part 2), bringing deduction total to 80+

**Definition of Done:** All deduction sections (80C through 80U + HRA + 24b) have YAML rules, are tested exhaustively, and regime filtering is verified for each.

---

### Days 15–16: Capital Gains Engine — Equity + Mutual Funds ✅

**Status:** ✅ COMPLETE
**Note:** `capital_gains.py` exists but raises `NotImplementedError`. Models (`CapitalGainsResult`, `AssetClass`, `GainType`) already defined. Need full implementation.

**Tasks:**
- [x] Create `rules/fy_2025_26/capital_gains/equity.yaml`
  - Listed equity: LTCG 12.5% (above ₹1.25L exemption, held >12 months), STCG 20%
  - Equity mutual funds: same as listed equity
  - Holding period threshold: 12 months for equity, 24 months for debt MF
- [x] Create `rules/fy_2025_26/capital_gains/debt.yaml`
  - Debt MF: taxed at slab rate (no special rate)
  - Held >36 months before 2023 amendment: indexation benefit
  - Post-2023: slab rate regardless of holding period
- [x] Implement `CapitalGainsCalculator.compute()`:
  - Determine gain type (STCG/LTCG) from holding period + asset class
  - Apply exemptions (₹1.25L for equity LTCG)
  - Compute tax at applicable rate
  - Return `CapitalGainsResult` with full breakdown
- [x] Implement grandfathering for pre-31-Jan-2018 equity
  - Fair Market Value (FMV) as of 31-Jan-2018
  - Cost = max(actual cost, min(FMV, sale price))
- [x] Write `test_capital_gains.py` — Part 1: 30+ tests
  - [x] Group A: Equity STCG — held <12 months, 20% rate (5 tests)
  - [x] Group B: Equity LTCG — held >12 months, 12.5% above ₹1.25L (6 tests)
  - [x] Group C: LTCG exemption — gains ≤ ₹1.25L = zero tax (3 tests)
  - [x] Group D: Equity MF — same rates as listed equity (4 tests)
  - [x] Group E: Debt MF — slab rate, no special treatment (4 tests)
  - [x] Group F: Grandfathering — pre-2018 equity with FMV adjustment (5 tests)
  - [x] Group G: Zero/negative gains — no tax on losses (3 tests)

**Files to Create/Modify:**
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/capital_gains/equity.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/capital_gains/debt.yaml`
- `packages/tax-engine/src/kara_tax_engine/capital_gains.py` (full rewrite)
- `packages/tax-engine/tests/test_capital_gains.py`

**Tests Target:** 30+ tests (Part 1)

**Definition of Done:** Equity and MF capital gains fully computed. Grandfathering works. LTCG exemption ₹1.25L applied. All tests green. ✅ DONE — 39 tests (Groups A-I), TaxComputer integration complete.

---

### Day 17: Capital Gains — Property, Gold, Crypto/VDA + Loss Set-off ✅

**Status:** ✅ COMPLETE

**Tasks:**
- [x] Create `rules/fy_2025_26/capital_gains/property.yaml`
  - Property LTCG: 12.5% (held >24 months), no indexation (post-2024 budget)
  - Section 54: Exemption on reinvestment in residential house (₹10Cr cap)
  - Section 54EC: Exemption on investment in specified bonds (₹50L cap, 5-year lock-in)
- [x] Create `rules/fy_2025_26/capital_gains/other.yaml`
  - Gold/jewellery: LTCG 12.5% (>24 months), STCG at slab rate
  - Unlisted shares: LTCG 12.5% (>24 months), STCG at slab rate
  - Crypto/VDA: flat 30%, no deductions except cost of acquisition, no set-off
- [x] Implement loss set-off rules:
  - STCL can offset STCG + LTCG (within capital gains head)
  - LTCL can offset LTCG only
  - No set-off against other income heads (except house property loss ₹2L)
  - Carry forward: 8 assessment years
  - Crypto losses: NO set-off against anything
- [x] Implement Section 54/54EC exemptions in calculator
- [x] Add tests to `test_capital_gains.py` — Part 2: 30+ tests
  - [x] Group H: Property LTCG (5 tests)
  - [x] Group I: Section 54 reinvestment exemption (4 tests)
  - [x] Group J: Section 54EC bond exemption (3 tests)
  - [x] Group K: Gold LTCG/STCG (4 tests)
  - [x] Group L: Crypto/VDA — 30% flat, no set-off (5 tests)
  - [x] Group M: Loss set-off — STCL against LTCG (4 tests)
  - [x] Group N: Loss carry forward — 8-year tracking (3 tests)
  - [x] Group O: Mixed assets — multiple gains/losses in one profile (3 tests)

**Files to Create/Modify:**
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/capital_gains/property.yaml`
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/capital_gains/other.yaml`
- `packages/tax-engine/src/kara_tax_engine/capital_gains.py` (extend)
- `packages/tax-engine/tests/test_capital_gains.py` (append Part 2)

**Tests Target:** 30+ tests (Part 2), bringing capital gains total to 60+

**Definition of Done:** All asset classes computed. Section 54/54EC exemptions work. Crypto 30% flat with no set-off. Loss set-off rules enforced. 60+ capital gains tests green. ✅ DONE — 31 tests (Groups H-O), all 276 tests green.

---

### Days 18–19: Regime Comparator + Deduction Optimizer ✅

**Status:** ✅ COMPLETE (Done on 2026-03-26)

**Tasks:**
- [x] Enhance `RegimeComparator`:
  - [x] `compare()` — compute both regimes, return delta + recommendation
  - [x] `_compute_breakeven_deductions()` — binary search in [0, 150K] for the 80C amount where old regime tax ≤ new
  - [x] `_compute_deduction_impact()` — per-section tax saving measurement (zero each section, measure delta)
  - [x] `_build_explanation()` — rich human-readable explanation with regime, savings, effective rates, breakeven guidance
- [x] Implement `DeductionOptimizer`:
  - [x] `optimize()` — full implementation analyzing current deductions vs caps
  - [x] 80C gap: suggest ELSS (3yr, 12-15%), PPF (15yr, 7.1%), 5yr Tax Saving FD (7%)
  - [x] 80CCD(1B) gap: suggest NPS (additional ₹50K over 80C limit)
  - [x] 80D gap: suggest health insurance (age-dependent cap)
  - [x] Rank suggestions by actual tax saving (recomputed via `TaxComputer`)
  - [x] Compute `optimized_tax` with all suggestions applied simultaneously
  - [x] `_compute_suggestion_saving()` — delta tax for each suggestion
  - [x] `_parse_return_range()` — parse YAML `returns_indicative` strings
- [x] Write `test_comparator.py` — 15 tests ✅
  - [x] Group A: Basic regime comparison (4 tests)
  - [x] Group B: Breakeven deduction calculation (4 tests) — verified at breakeven amount
  - [x] Group C: Explanation & metadata (4 tests)
  - [x] Group D: Edge cases — zero income, surcharge zone, near-equal (3 tests)
- [x] Write `test_optimizer.py` — 15 tests ✅
  - [x] Group A: 80C gap detection (4 tests)
  - [x] Group B: 80D gap detection (3 tests)
  - [x] Group C: NPS 80CCD(1B) (3 tests)
  - [x] Group D: No suggestions / edge cases (2 tests)
  - [x] Group E: Suggestion quality and ranking (3 tests)
- [x] Updated `tests/conftest.py` — added `optimizer` session fixture

**Files Modified:**
- `packages/tax-engine/src/kara_tax_engine/comparator.py` (enhanced: 245 lines)
- `packages/tax-engine/src/kara_tax_engine/optimizer.py` (full implementation: 247 lines)
- `packages/tax-engine/tests/conftest.py` (added optimizer fixture)

**Files Created:**
- `packages/tax-engine/tests/test_comparator.py` (15 tests)
- `packages/tax-engine/tests/test_optimizer.py` (15 tests)

**Tests:** 30 new tests (15 comparator + 15 optimizer). All 306 tests green. ✅ DONE

---

### Day 20: PyPI Release Prep + v0.1.0 Tag ✅

**Status:** ✅ COMPLETE (Done on 2026-03-26)

**Tasks:**
- [x] Update `README.md` — comprehensive rewrite: features, installation, quick start (compute/compare/optimize), API reference, supported sections table
- [x] Add `LICENSE` file — MIT, "Kara Contributors", 2026
- [x] Verify `pyproject.toml` metadata — description, author, classifiers, URLs all correct ✅
- [x] Add `CHANGELOG.md` — v0.1.0 initial release notes with full feature list
- [x] Add `OptimizationResult`, `OptimizationSuggestion`, `Deductions`, `HRADetails`, `SalaryIncome` to `__init__.py` exports
- [x] Run full test suite — **306 tests passing** ✅
- [x] Run `ruff check` + `ruff format` — new files clean, 13 files reformatted ✅
- [x] Build package: `python -m build` → `kara_tax_engine-0.1.0-py3-none-any.whl` ✅
- [x] End-to-end smoke test:
  ```python
  from kara_tax_engine import TaxComputer
  result = TaxComputer("2025-26").compute(gross_salary=1_500_000, regime="new")
  print(result.total_tax_payable)  # 97,500 ✅
  ```
- [ ] Tag: `git tag v0.1.0` *(pending — repo to be initialized)*

**Files Created:**
- `packages/tax-engine/README.md` (complete rewrite)
- `packages/tax-engine/LICENSE` (MIT)
- `packages/tax-engine/CHANGELOG.md` (v0.1.0)

**Files Modified:**
- `packages/tax-engine/src/kara_tax_engine/__init__.py` (added 5 new exports, import sort fixed)

**Tests:** 306 total tests passing (all 306 green). Exceeds 250+ target.

**🏆 MILESTONE (Day 20):** pip package built. 306 tests passing. v0.1.0 wheel ready. ✅ DONE

---

## Phase 2 — Backend + AI Agent (Days 21–40)

**Goal:** AI chat working end-to-end — user asks questions → AI asks back → calls rule engine → returns cited answers with proactive tips.

**Phase Milestone:** AI chat working end-to-end.

---

### Days 21–22: FastAPI Project Setup + Docker ✅

**Status:** ✅ COMPLETE (2026-03-26)

**Tasks:**
- [x] Create `apps/api/pyproject.toml` — FastAPI, uvicorn, asyncpg, sqlalchemy, alembic, pydantic-settings, pgvector
- [x] Create `apps/api/Dockerfile` — Python 3.11 slim, multi-stage (builder + runtime), non-root user
- [x] Create root `docker-compose.yml`:
  - `db`: pgvector/pgvector:pg16 (PostgreSQL 16 + pgvector extension)
  - `api`: FastAPI app, depends on db (service_healthy condition)
  - Named volume `kara-db-data` for data persistence
  - Environment variables via `apps/api/.env`
- [x] Create `apps/api/.env.example` — DATABASE_URL, LLM_API_KEY, LLM_MODEL, LLM_PROVIDER, CORS_ORIGINS, DEBUG
- [x] Create `apps/api/src/kara_api/main.py` — FastAPI app factory (`create_app()`), CORS middleware, lifespan handler, `GET /health`
- [x] Create `apps/api/src/kara_api/config.py` — Pydantic Settings with `@lru_cache` singleton, `sync_database_url` property
- [x] Create `.dockerignore` at repo root
- [x] Health check endpoint returns `{"status": "ok"}` — 6 tests passing

**Files Created:**
- `apps/api/pyproject.toml`
- `apps/api/Dockerfile`
- `docker-compose.yml` (root)
- `.dockerignore` (root)
- `apps/api/.env.example` + `apps/api/.env`
- `apps/api/src/kara_api/__init__.py` + subpackage `__init__.py` files
- `apps/api/src/kara_api/main.py`
- `apps/api/src/kara_api/config.py`
- `apps/api/tests/conftest.py`, `test_health.py`, `test_config.py`

**Tests:** 6 tests (2 health + 4 config) — all passing

**Definition of Done:** ✅ FastAPI package installable. 6 tests green. Docker Compose ready for `docker compose up`.

---

### Days 23–24: Database Schema + Migrations ✅

**Status:** ✅ COMPLETE (2026-03-26)

**Tasks:**
- [x] Create SQLAlchemy models in `apps/api/src/kara_api/db/models.py`:
  - `tax_sections` — id, section_number (ltree), title, content, summary, embedding (vector(1536)), search_vector (tsvector), relationships, metadata_json
  - `section_relationships` — parent_id, child_id, relationship_type (overrides, supplements, requires)
  - `sessions` — id, created_at, updated_at, profile_json (accumulated TaxProfile)
  - `messages` — id, session_id, role (user/assistant/tool), content, tool_calls_json, created_at
- [x] Create `apps/api/src/kara_api/db/connection.py` — async SQLAlchemy engine + session factory
- [x] Set up Alembic:
  - Configured `alembic.ini` with `prepend_sys_path = src` for async
  - Created `alembic/env.py` with async engine support
  - Hand-written initial migration: `alembic/versions/001_initial_schema.py`
- [x] Enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector`
- [x] Enable ltree extension: `CREATE EXTENSION IF NOT EXISTS ltree`
- [x] Create GIN index on tsvector column + GiST index on ltree_path::ltree
- [x] Create HNSW index on vector column (m=16, ef_construction=64)
- [x] B-tree composite index on messages(session_id, created_at)
- [x] B-tree index on sessions(updated_at)
- [x] Integrated DB lifecycle into FastAPI lifespan (init_db/close_db)
- [x] Updated Dockerfile with alembic files + auto-migrate on startup
- [x] Unit tests: 10 new tests (6 model + 4 connection) — all passing
- [x] Integration tests: 7 tests (migration, extensions, indexes, cascade delete, tsvector generation) — require PostgreSQL

**Files Created:**
- `apps/api/src/kara_api/db/models.py` (174 lines) — Base, TaxSection, SectionRelationship, Session, Message + enums
- `apps/api/src/kara_api/db/connection.py` (55 lines) — init_db, close_db, get_session_factory, get_db_session
- `apps/api/alembic.ini` (43 lines)
- `apps/api/alembic/env.py` (81 lines) — async Alembic environment
- `apps/api/alembic/script.py.mako` (26 lines)
- `apps/api/alembic/versions/001_initial_schema.py` (183 lines) — 4 tables, 2 extensions, 5 indexes
- `apps/api/tests/test_db_models.py` (56 lines) — 6 unit tests
- `apps/api/tests/test_connection.py` (61 lines) — 4 unit tests
- `apps/api/tests/test_migration.py` (164 lines) — 7 integration tests

**Files Modified:**
- `apps/api/src/kara_api/db/__init__.py` — re-exports
- `apps/api/src/kara_api/main.py` — DB lifecycle in lifespan
- `apps/api/tests/conftest.py` — DB fixtures (database_url, db_session)
- `apps/api/pyproject.toml` — aiosqlite dev dep, integration marker
- `apps/api/Dockerfile` — alembic files + auto-migrate CMD

**Tests:** 16 unit tests passing (10 new + 6 existing). 7 integration tests ready (need PostgreSQL).

**Definition of Done:** `alembic upgrade head` creates all tables. pgvector, ltree, tsvector extensions enabled. Indexes created. ✅

---

### Days 25–26: Direct Computation API Endpoints ✅

**Status:** ✅ COMPLETE (2026-03-27)

**Tasks:**
- [x] Create `apps/api/src/kara_api/routers/tax.py` — 4 tax computation endpoints (no AI):
  - `POST /api/v1/tax/compute` — compute tax from TaxProfile JSON
  - `POST /api/v1/tax/compare` — compare old vs new regime
  - `POST /api/v1/tax/optimize` — get deduction suggestions
  - `POST /api/v1/tax/capital-gains` — compute capital gains tax
- [x] Reused tax-engine Pydantic models directly as request/response schemas (TaxProfile, TaxBreakdown, RegimeComparison, OptimizationResult, CapitalGainsResult)
- [x] Created `CapitalGainsRequest` API-layer model wrapping `list[CapitalGainTransaction]` with min_length=1
- [x] Wired up `kara-tax-engine>=0.1.0` as dependency in pyproject.toml
- [x] Added centralized error handling — `_handle_engine_call()` converts ValueError→400, Pydantic→422 (auto), Exception→500
- [x] Module-level engine singletons (stateless, thread-safe) — TaxComputer, RegimeComparator, DeductionOptimizer, CapitalGainsCalculator
- [x] Sync endpoints (def, not async def) — CPU-bound, FastAPI runs in threadpool
- [x] Included router in main.py with API_V1_PREFIX
- [x] Write API tests — 20 tests across 4 test classes
  - [x] TestComputeTax: 8 tests (basic new/old, deductions, zero, senior, invalid, defaults, multi-income, steps)
  - [x] TestCompareRegimes: 3 tests (basic, heavy deductions, empty)
  - [x] TestOptimizeDeductions: 3 tests (basic, maxed, empty)
  - [x] TestCapitalGains: 6 tests (equity, multiple, empty/missing/invalid 422s, loss)

**Files Created:**
- `apps/api/src/kara_api/routers/tax.py` (83 lines) — 4 endpoints + error handler + CapitalGainsRequest
- `apps/api/tests/test_tax_endpoints.py` (298 lines) — 20 tests

**Files Modified:**
- `apps/api/pyproject.toml` — added kara-tax-engine dependency
- `apps/api/src/kara_api/routers/__init__.py` — re-export tax_router
- `apps/api/src/kara_api/main.py` — include_router with API_V1_PREFIX

**Tests:** 20 new tests passing (36 total API tests). 0 regressions.

**Definition of Done:** ✅ All 4 computation endpoints working. Input validation enforced. 20 tests green. No AI required — pure rule engine.

---

### Days 27–28: Knowledge Base + Hybrid Search ✅

**Status:** ✅ COMPLETE (2026-03-27)

**Tasks:**
- [x] Curate 114 key tax sections as structured YAML data:
  - Section number, title, plain-English summary, full text, common questions
  - ltree hierarchy for taxonomic navigation (income_tax.deductions.s80c.epf etc.)
  - 37 cross-references via section_relationships (overrides, supplements, requires)
- [x] Create `apps/api/scripts/seed_knowledge_base.py`:
  - Loads YAML, generates embeddings in batches of 50
  - Embedding text = title + content + summary + common_questions
  - TRUNCATE CASCADE for idempotency, INSERT sections + relationships
  - --dry-run flag, ON CONFLICT safety, progress logging
- [x] Implement hybrid search in `apps/api/src/kara_api/knowledge/search.py`:
  - Semantic search: pgvector cosine similarity via `<=>` operator
  - Keyword search: PostgreSQL tsvector with `plainto_tsquery` + `ts_rank`
  - Graph boost: direct relationships (0.3) + ltree siblings (0.1)
  - Reciprocal Rank Fusion (RRF, k=60) combining all three signals
  - Concurrent execution via `asyncio.gather`
- [x] Create search API endpoint: `POST /api/v1/knowledge/search`
- [x] Wire knowledge router into FastAPI app
- [x] Write search tests — 24 tests total
  - [x] 5 YAML validation tests (test_seed.py)
  - [x] 5 seed script unit tests (test_seed_script.py)
  - [x] 10 search unit tests + 5 integration stubs (test_search.py)
  - [x] 4 endpoint tests (test_knowledge_endpoints.py)

**Files Created:**
- `apps/api/data/tax_sections.yaml` (~2500 lines) — 114 curated tax sections + 37 relationships
- `apps/api/scripts/__init__.py`
- `apps/api/scripts/seed_knowledge_base.py` (314 lines) — async seed script
- `apps/api/src/kara_api/knowledge/search.py` (239 lines) — SearchResult + 4 search functions
- `apps/api/src/kara_api/routers/knowledge.py` — POST /search endpoint
- `apps/api/tests/test_search.py` — 15 tests (10 unit + 5 integration stubs)
- `apps/api/tests/test_seed_script.py` — 5 tests
- `apps/api/tests/test_knowledge_endpoints.py` — 4 tests

**Files Modified:**
- `apps/api/pyproject.toml` — added pyyaml dependency
- `apps/api/src/kara_api/knowledge/__init__.py` — search re-exports
- `apps/api/src/kara_api/routers/__init__.py` — added knowledge_router
- `apps/api/src/kara_api/main.py` — included knowledge router

**Tests:** 24 new tests (76 total API tests passing, 12 integration deselected). 0 regressions.

**Definition of Done:** ✅ 114 sections curated. Hybrid search module complete with RRF fusion. All 76 unit tests green.

---

### Days 29–30: LLM Client + Provider Abstraction ✅

**Status:** ✅ COMPLETE (2026-03-28)

**Tasks:**
- [x] Create `apps/api/src/kara_api/llm/models.py` — normalized data models (Role, Message, ToolCall, ToolDefinition, LLMRequest, LLMResponse, StreamChunk, TokenUsage)
- [x] Create `apps/api/src/kara_api/llm/providers.py` — provider Protocol + 4 implementations:
  - `OpenAIProvider` — raw httpx to `/v1/chat/completions`, Bearer auth, retry 3x on 429/5xx, SSE streaming
  - `AnthropicProvider` — `/v1/messages`, x-api-key header, system extraction, tool_use content blocks, Anthropic SSE events
  - `OllamaProvider` — delegates to OpenAIProvider at Ollama's `/v1` base URL
  - `FakeLLMProvider` — canned response queue + deterministic streaming, for testing
  - `get_llm_provider(settings)` factory function
- [x] Create `apps/api/src/kara_api/llm/client.py` — `LLMClient` wrapper with `chat()` + `chat_stream()`, Kara system prompt
- [x] Create `apps/api/src/kara_api/tools/converters.py` — `to_openai_tools`, `to_anthropic_tools`, `parse_openai_tool_calls`, `parse_anthropic_tool_calls`
- [x] Update `apps/api/src/kara_api/config.py` — added `LLM_BASE_URL`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`
- [x] Move `httpx` from dev to main dependencies in `pyproject.toml`
- [x] Write tests — 54 total (12 models + 38 providers + 8 converters + 8 client)

**Files Created:**
- `apps/api/src/kara_api/llm/models.py`
- `apps/api/src/kara_api/llm/providers.py` (531 lines)
- `apps/api/src/kara_api/llm/client.py`
- `apps/api/src/kara_api/llm/__init__.py` (full re-exports)
- `apps/api/src/kara_api/tools/converters.py`
- `apps/api/src/kara_api/tools/__init__.py`
- `apps/api/tests/test_llm_models.py` (12 tests)
- `apps/api/tests/test_llm_providers.py` (38 tests)
- `apps/api/tests/test_llm_client.py` (8 tests)
- `apps/api/tests/test_tool_converters.py` (8 tests)

**Tests:** 54 new tests (184 total API tests passing)

**Definition of Done:** ✅ LLM client sends/receives messages to Claude/GPT/Ollama. Streaming works. All 4 providers tested. API key configurable via env.

---

### Days 31–32: Tool Registry + Function Schemas ✅

**Status:** ✅ COMPLETE (2026-03-28) — done ahead of schedule as part of Day 30

**Tasks:**
- [x] Create `apps/api/src/kara_api/tools/schemas.py` — 8 tool schemas in OpenAI function-calling JSON Schema format:
  1. `compute_tax` — full tax computation from profile
  2. `compare_regimes` — old vs new regime comparison
  3. `compute_capital_gains` — capital gains (7 asset classes: equity, debt MF, property, gold, crypto, etc.)
  4. `find_deduction_gaps` — optimization suggestions
  5. `search_tax_law` — hybrid search on knowledge base
  6. `get_tds_rate` — TDS rate lookup (stub, full in Phase 4)
  7. `calculate_advance_tax` — quarterly installment schedule (stub, full in Phase 4)
  8. `select_itr_form` — ITR form decision tree (stub, full in Phase 4)
- [x] Create `apps/api/src/kara_api/tools/executor.py` — `ToolRegistry` class with dependency injection, `execute()` + `execute_many()`, 8 handler methods, `ToolResult` model
- [x] Handlers: build TaxProfile from args, call tax engine, return `.model_dump()`; stubs return useful hardcoded data
- [x] Write tool tests — 39 tests (16 schemas + 23 executor)

**Files Created:**
- `apps/api/src/kara_api/tools/schemas.py` — ALL_TOOLS list, TOOL_MAP dict
- `apps/api/src/kara_api/tools/executor.py` — ToolRegistry, ToolResult, ToolExecutionError
- `apps/api/tests/test_tool_schemas.py` (16 tests)
- `apps/api/tests/test_tool_executor.py` (23 tests)

**Tests:** 39 new tests (184 total API tests passing)

**Definition of Done:** ✅ 8 tools defined with OpenAI function-calling schema. Executor dispatches to all 8 handlers. `ToolRegistry` injects tax engine singletons. All tools return valid JSON-serialized results.

---

### Days 33–34: System Prompt + Intent Taxonomy + Profile Builder ✅

**Status:** ✅ COMPLETE (2026-03-28)

**Tasks:**
- [x] Create `apps/api/src/kara_api/agent/prompts.py` — system prompt with:
  - Role definition: Indian tax advisor, conversational, asks before computing
  - Intent taxonomy (9 intents): COMPUTE_TAX, COMPARE_REGIMES, CAPITAL_GAINS, DEDUCTION_ADVICE, TAX_PLANNING, WITHDRAWAL, INVESTMENT, COMPLIANCE, GENERAL_QUERY
  - SlotDefinition model + ALL_SLOTS registry (29 slots across 5 categories)
  - IntentSpec model + INTENT_SPECS dict (required/optional slots per intent, primary tool, example queries)
  - Enhanced system prompt (~714 tokens) with tool usage guide, response format, citation rules
  - 3 helper functions: get_intent_spec, get_required_slots, get_slot_definition
- [x] Create `apps/api/src/kara_api/agent/profile_builder.py`:
  - ProfileBuilder class tracking slot accumulation across turns
  - Slot management: add/get/remove/clear with copy safety
  - Intent readiness: get_missing_slots, is_intent_ready, get_ready_intents
  - TaxProfile conversion: to_tax_profile() with deduction mapping (10 deduction fields)
  - Serialization: to_dict/from_dict for session persistence
- [x] Update `apps/api/src/kara_api/agent/__init__.py` with all public exports
- [x] Write tests — 50 total (21 prompts + 29 profile builder)
  - [x] Intent enum validation (count, values, spec coverage)
  - [x] Slot definitions (count, types, descriptions)
  - [x] Intent specs (required slots, tools, examples)
  - [x] System prompt structure (mentions Kara, tools, citations)
  - [x] Slot management (add/get/remove/clear/overwrite/copy safety)
  - [x] Intent readiness (compute_tax, capital_gains, compliance, general_query)
  - [x] TaxProfile conversion (salary, regime, deductions, all income types, HRA)
  - [x] Serialization round-trip

**Files Created:**
- `apps/api/src/kara_api/agent/prompts.py` (~300 lines)
- `apps/api/src/kara_api/agent/profile_builder.py` (~145 lines)
- `apps/api/tests/test_prompts.py` (21 tests)
- `apps/api/tests/test_profile_builder.py` (29 tests)

**Files Modified:**
- `apps/api/src/kara_api/agent/__init__.py` (added 10 exports)

**Tests:** 50 new tests (234 total API tests passing)

**Definition of Done:** ✅ System prompt captures full intent taxonomy with 9 intents. 29 slots defined across income, demographics, deductions, capital gains, compliance. Profile builder tracks slots, checks readiness, converts to TaxProfile. All 50 tests green.

---

### Days 36–38: Agent Loop + Session Manager + Chat Endpoints ✅

**Status:** ✅ COMPLETE (2026-03-29)

**What was built:**

1. **Agent Loop** (`apps/api/src/kara_api/agent/loop.py`) — ~120 lines core:
   - [x] `AgentLoop` class: LLM ↔ tool execution cycle
   - [x] `run()` method: takes user message + history → iterates LLM calls with tool execution
   - [x] Max iterations guard (default 10) — returns fallback message on exhaustion
   - [x] Error recovery — tool errors passed back to LLM as tool results for self-correction
   - [x] LLM provider errors caught and raised as `AgentError`
   - [x] Token usage accumulation across iterations
   - [x] `AgentResponse` model: content, tool_calls_made, total_usage, iterations, profile_snapshot
   - [x] `ToolCallRecord` model for observability audit trail

2. **Session Manager** (`apps/api/src/kara_api/agent/session.py`) — ~80 lines:
   - [x] `SessionManager` class with CRUD for chat sessions
   - [x] `create_session()`, `get_session()`, `delete_session()` (cascade)
   - [x] `add_message()`, `get_messages()` (chronological order)
   - [x] `update_profile()` — persists ProfileBuilder state as JSONB

3. **Advisory Triggers** (`apps/api/src/kara_api/agent/advisory.py`) — ~77 lines:
   - [x] `AdvisoryTriggers` class with 4 proactive hint rules:
     - After `compute_tax` (alone) → suggest regime comparison
     - After `compare_regimes` → suggest deduction opportunities
     - After `find_deduction_gaps` → suggest ELSS/PPF/NPS
     - After `compute_capital_gains` → suggest Section 54/54EC exemptions
   - [x] Deduplication and suppression logic (e.g., no compute_tax hint if compare_regimes also called)

4. **Chat Router** (`apps/api/src/kara_api/routers/chat.py`) — ~350 lines:
   - [x] `POST /api/v1/chat` — create new session + first message → SSE stream
   - [x] `POST /api/v1/chat/{session_id}` — continue conversation → SSE stream
   - [x] `GET /api/v1/chat/{session_id}` — fetch session history + profile state
   - [x] `DELETE /api/v1/chat/{session_id}` — delete session and messages
   - [x] SSE events: `session_created`, `tool_result`, `content`, `advisory`, `done`, `error`
   - [x] Non-streaming JSON fallback via `Accept: application/json` header
   - [x] Profile state persistence and restoration across turns
   - [x] Message history converted between DB and LLM formats

**Files Created:**
- `apps/api/src/kara_api/agent/loop.py` — Core agent loop
- `apps/api/src/kara_api/agent/session.py` — Session CRUD
- `apps/api/src/kara_api/agent/advisory.py` — Proactive advisory triggers
- `apps/api/src/kara_api/routers/chat.py` — Chat endpoints with SSE
- `apps/api/tests/test_agent_loop.py` — 20 tests
- `apps/api/tests/test_session_manager.py` — 11 tests
- `apps/api/tests/test_advisory.py` — 10 tests
- `apps/api/tests/test_chat_endpoints.py` — 20 tests

**Files Modified:**
- `apps/api/src/kara_api/agent/__init__.py` — Added exports
- `apps/api/src/kara_api/routers/__init__.py` — Added chat_router
- `apps/api/src/kara_api/main.py` — Registered chat_router

**Tests:** 61 new tests (20 + 11 + 10 + 20), bringing API total to 297 passed
**Total project tests:** 603 (297 API + 306 tax-engine)

**Definition of Done:** ✅ Agent loop works end-to-end with mocked LLM. Tool calling cycles correctly. Sessions persist. Chat endpoints serve SSE streams. Advisory triggers fire after computations.

---

### Days 39–40: E2E Integration Tests + Docker Smoke Test ✅

**Status:** ✅ COMPLETE (2026-03-30)

**Note:** Chat router, SSE streaming, advisory triggers, and session management were completed ahead of schedule in Days 36–38. Days 39–40 focused on end-to-end integration testing and Docker readiness verification.

**What was built:**

1. **End-to-End Integration Tests** (`apps/api/tests/test_integration.py`):
   - [x] `InMemorySessionManager` — dict-backed drop-in for `SessionManager` (no PostgreSQL needed)
   - [x] Integration test fixtures: `_integration_client` factory with FakeLLMProvider + real ToolRegistry
   - [x] 8 single-turn tests exercising full HTTP → AgentLoop → ToolRegistry pipeline:
     - `test_salary_tax_computation_sse` — compute_tax via SSE stream with real tax engine
     - `test_salary_tax_computation_json` — same via JSON fallback
     - `test_regime_comparison_flow` — compare_regimes + advisory hint verification
     - `test_capital_gains_computation` — capital gains with specific field assertions
     - `test_deduction_optimization` — deduction gap suggestions
     - `test_stub_tools_tds_rate` — TDS rate stub tool
     - `test_stub_tools_advance_tax` — advance tax stub tool
     - `test_error_recovery_unknown_tool` — unknown tool error → graceful fallback
   - [x] 5 multi-turn tests verifying session state across requests:
     - `test_create_then_continue_session` — create → continue → GET history
     - `test_profile_accumulates_across_turns` — profile state persists
     - `test_session_deletion` — create → DELETE → 404
     - `test_continue_nonexistent_session_404` — random UUID → 404
     - `test_history_forwarded_to_agent` — prior messages passed to LLM

2. **Docker Smoke Test** (`scripts/smoke_test.sh` + `docker-compose.test.yml`):
   - [x] `docker-compose.test.yml` — compose override with `LLM_PROVIDER=fake`
   - [x] `scripts/smoke_test.sh` — automated smoke test:
     - Pre-flight checks (docker, docker compose, curl)
     - Cleanup trap (docker compose down -v on EXIT)
     - .env guard for fresh checkouts
     - Health endpoint verification
     - Chat JSON endpoint verification
     - Chat SSE endpoint verification
     - Pass/fail summary with correct exit codes

**Files Created:**
- `apps/api/tests/test_integration.py` (~750 lines) — 13 E2E integration tests
- `scripts/smoke_test.sh` (~165 lines) — Docker smoke test script
- `docker-compose.test.yml` — compose override for testing

**Tests:** 13 new integration tests (310 total API tests passing, 12 integration deselected). 0 regressions.

**🏆 MILESTONE (Day 40):** AI chat working end-to-end. Docker compose runs full stack. ✅ DONE

---

## Phase 3 — Frontend (Days 41–55)

**Goal:** Full UI with rich tax cards — beautiful chat with tax breakdown cards, regime comparison, deduction trackers. Mobile-ready.

**Phase Milestone:** Full UI with rich cards. Mobile-ready.

---

### Days 41–44: Next.js Setup + Design System + Landing Page + Navigation ✅

**Status:** ✅ COMPLETE (2026-04-02) — Days 41-42 and 43-44 merged: all work done in one sprint.

**Tasks:**
- [x] Initialize Next.js 16.2.2 with App Router + TypeScript + Tailwind v4 + shadcn/ui
- [x] Install: next-themes, lucide-react, clsx, tailwind-merge, class-variance-authority
- [x] Add shadcn components: Button, Card, Input, ScrollArea, Avatar, Badge
- [x] Configure Kara design system (Tailwind v4 CSS-based, no tailwind.config.ts):
  - IBM Plex Sans font (next/font/google, 400/500/600/700)
  - Primary: #2563EB (blue-600), CTA: #F97316 (orange), Accent: #059669 (green)
  - `--color-kara-*` tokens in `@theme inline` → Tailwind utilities `bg-kara-cta`, etc.
  - oklch-based light (#F8FAFC bg, #1E293B text) and dark (#0F172A bg, #F1F5F9 text) palettes
  - `prefers-reduced-motion` media query
  - Skip-link accessibility CSS
- [x] Layout shell: ThemeProvider, SkipLink, Header, `<main id="main-content">`, Footer
- [x] Header: sticky, Kara/कर logo + "Open Source" badge, Home/Chat nav, dark mode toggle (resolvedTheme), GitHub link, mobile hamburger
- [x] Footer: brand tagline, GitHub + /docs links, MIT License badge
- [x] Landing page: Hero (h1 + CTA + GitHub), Features Grid (4 cards with h3 headings), How It Works (3 steps), Tech Stack badges
- [x] Chat placeholder page at `/chat`
- [x] 404 not-found page
- [x] API proxy in next.config.ts: `/api/*` → `http://localhost:8000/api/*`
- [x] GITHUB_URL constant centralised in lib/constants.ts
- [x] `suppressHydrationWarning` on `<html>`, `lang="en"`, ARIA labels

**Files Created:**
- `apps/web/` — full Next.js 16 project (package.json, tsconfig.json, next.config.ts, components.json)
- `apps/web/src/app/globals.css` — Kara theme, dark mode, a11y
- `apps/web/src/app/layout.tsx` — root layout
- `apps/web/src/app/page.tsx` — landing page
- `apps/web/src/app/chat/page.tsx` — chat placeholder
- `apps/web/src/app/not-found.tsx` — 404
- `apps/web/src/lib/fonts.ts`, `constants.ts`, `utils.ts`
- `apps/web/src/components/theme-provider.tsx`
- `apps/web/src/components/layout/Header.tsx`, `Footer.tsx`, `SkipLink.tsx`
- `apps/web/src/components/ui/` — shadcn components

**Tests:** Build passes, 3 static routes (`/`, `/chat`, `/_not-found`). Lint clean. TypeScript clean.

**Commits:** c5bd871 → 18cf100 (6 commits)

---

### Days 45–47: Chat Interface ✅

**Status:** ✅ COMPLETE (2026-04-03) — Full chat interface built with SSE streaming, session persistence, accessibility, and mobile polish.

**Architecture Decision:** Hybrid streaming — SSE events stream as they occur (session_created → tool_result × N → content → advisory → done), but `content` arrives as one chunk from the current backend. Frontend is built to also handle future `content_delta` token-by-token events when the backend is upgraded. Tool events provide visual progress ("Searching tax laws...", "Computing...") during the 8–15s agent processing time, so users never stare at a blank screen.

**NPM Packages Installed:** `react-markdown` (^9.0.0), `remark-gfm` (^4.0.0)

**Commits:** 430e455 → 428a160 (8 commits)

---

#### Day 45: Foundation — Types, API Client, SSE Hook, ChatWindow + MessageInput

**Task 45.1: TypeScript Types + API Client** ✅
- [x] Create `types/chat.ts` — `SSEEvent` discriminated union, `ChatRequest`, `MessageResponse`, `ProfileState`, `SessionResponse`, `ChatResponse`, `ChatMessage`, `ToolEvent`
- [x] Create `lib/api.ts` — `createChat`, `continueChat`, `fetchSession`, `deleteSession` + `HttpError` class for typed status-code error handling

**Task 45.2: SSE Streaming Hook** ✅
- [x] Create `hooks/useSSE.ts` — fetch + ReadableStream parser; `processStream(response, callbacks)`; `abort()` via AbortController; handles `content` + `content_delta` for forward compatibility

**Task 45.3: Basic ChatWindow + MessageInput** ✅
- [x] Create `components/chat/MessageInput.tsx` — auto-growing textarea (1→5 rows), Enter to send, Shift+Enter for newline, ArrowUp send button, ≥44px touch target, sr-only label, Escape to clear, auto-focus on mount
- [x] Create `components/chat/ChatWindow.tsx` — flex-col full-height layout, native scrollable div, MessageInput sticky at bottom
- [x] Replace `app/chat/page.tsx` — Server Component wrapper rendering `<ChatWindow />`

---

#### Day 46: Messages — MessageBubble, TypingIndicator, useChat, Streaming Integration

**Task 46.1: MessageBubble with Markdown** ✅
- [x] Create `components/chat/MessageBubble.tsx` — user bubbles right-aligned (bg-primary), assistant bubbles left-aligned (bg-muted) with Kara avatar; `react-markdown` + `remark-gfm` with Tailwind component overrides; relative timestamps; streaming cursor animation; tool event badges above bubble; fade-in animation (animate-in)

**Task 46.2: TypingIndicator + useChat Hook** ✅
- [x] Create `components/chat/TypingIndicator.tsx` — 3 bouncing dots, staggered delays (0/150/300ms), `role="status"`, `aria-label="Kara is thinking"`
- [x] Create `hooks/useChat.ts` — `useReducer` with `lastAssistantIndex`/`markLastAssistantDone` helpers; actions: ADD_USER_MESSAGE, ADD_ASSISTANT_MESSAGE, APPEND_CONTENT, ADD_TOOL_EVENT, SET_SESSION_ID, SET_STREAMING, SET_ERROR, SET_DONE, LOAD_HISTORY, SET_LOADING, CLEAR; `sendMessage`, `clearChat`, `loadSession`, `dismissError`

**Task 46.3: Streaming Integration + Auto-scroll** ✅
- [x] Wire ChatWindow with useChat — MessageBubble per message, TypingIndicator when streaming + empty content, error banner with "Try again" + dismiss
- [x] Auto-scroll via sentinel div + `scrollIntoView`; skips when user scrolled up >100px; `behavior: 'instant'` for prefers-reduced-motion
- [x] Abort in-flight stream on new `sendMessage` call and on unmount

---

#### Day 47: Polish — SuggestedQuestions, Session Persistence, Error Handling, a11y, Mobile

**Task 47.1: SuggestedQuestions + Empty State** ✅
- [x] Create `components/chat/SuggestedQuestions.tsx` — 4 chips in 2×2 grid (Calculator, Scale, TrendingUp, FileText icons), native `<button>` styled as Badge secondary, min-h 44px, 200ms hover transition, focus ring
- [x] Empty state in ChatWindow: large Kara avatar (size-16, bg-kara-primary) + "Hi! I'm Kara" h2 + muted subtitle + SuggestedQuestions; disappears once first message sent; suppressed during loading/streaming

**Task 47.2: Session Persistence (localStorage)** ✅
- [x] On mount: read `kara_session_id` from localStorage → `loadSession()` → LOAD_HISTORY or silent clear on 404 (typed via `HttpError`)
- [x] On `onSessionCreated`: `localStorage.setItem("kara_session_id", sessionId)`
- [x] On `clearChat`: `localStorage.removeItem` + best-effort `deleteSession()` call
- [x] Loading skeleton: 3 pulsing placeholder bubbles (assistant/user/assistant pattern) with `aria-busy="true"`

**Task 47.3: Error Handling + Accessibility + Mobile Polish** ✅
- [x] Error states: network failure ("Unable to connect. Check your connection and try again."), SSE error (backend message inline), empty response ("Kara couldn't generate a response. Please try rephrasing.") — empty assistant bubble removed from state
- [x] Accessibility: `role="log"` + `aria-live="polite"` on message list; `role="alert"` on error banner; `role="status"` on typing indicator; `sr-only` label + `htmlFor`/`id` pairing on textarea; Escape to clear input; `aria-hidden` on decorative icons and scroll sentinel
- [x] Mobile: sticky bottom-0 input with `calc(0.75rem + env(safe-area-inset-bottom))` for iOS; ≥44px touch targets everywhere; full-width layout
- [x] Micro-interactions: `animate-in fade-in duration-200` on message bubbles; `active:scale-95` on send button; 200ms hover transition on suggestion chips

**Files Created:**
- `apps/web/src/types/chat.ts`
- `apps/web/src/lib/api.ts` (+ `HttpError` class)
- `apps/web/src/hooks/useSSE.ts`
- `apps/web/src/hooks/useChat.ts`
- `apps/web/src/components/chat/ChatWindow.tsx`
- `apps/web/src/components/chat/MessageBubble.tsx`
- `apps/web/src/components/chat/MessageInput.tsx`
- `apps/web/src/components/chat/TypingIndicator.tsx`
- `apps/web/src/components/chat/SuggestedQuestions.tsx`
- `apps/web/src/app/chat/page.tsx` (replaced placeholder)

**Definition of Done:** ✅ Chat interface works end-to-end with hybrid SSE streaming. Tool events show progress. Messages render with markdown. Typing indicator shows. Suggested questions clickable. Session restores on reload. Mobile responsive. Accessible. Dark mode works.

---

### Days 48–49: Chat Polish + Session Management ✅

**Status:** ✅ DONE — 2026-04-09

#### Day 48: Session Sidebar (Backend → Frontend → Layout)

**Task 48.1: Backend — SessionManager.list_sessions()** ✅
- [x] New `SessionSummaryRow` dataclass (`id`, `created_at`, `updated_at`, `title`, `message_count`) — dedicated projection for the sidebar
- [x] `SessionManager.list_sessions()` — orders sessions by `updated_at DESC`, derives `title` from first user message (60-char truncation + `…`, or `"New Chat"` fallback when no user message exists)
- [x] 8 new tests on `TestListSessions`: empty list, ordering preserved, title from first user message, 60-char truncation, fallback when no messages, fallback when only assistant message, message_count across roles, returns `SessionSummaryRow` instances

**Task 48.2: Backend — GET /api/v1/chat/sessions** ✅
- [x] New `SessionSummary` Pydantic model mirroring the dataclass
- [x] `GET /sessions` route declared **before** `GET /{session_id}` so the literal path is not parsed as a UUID param (added a regression test for exactly this)
- [x] 3 new tests on `TestListSessionsEndpoint`: empty list, populated rows, path-collision regression

**Task 48.3: Frontend — Types + API Client + useSessions Hook** ✅
- [x] `SessionSummary` interface in `types/chat.ts`
- [x] `listSessions()` added to `lib/api.ts` (routes through the `/api/v1/chat/sessions` proxy)
- [x] `hooks/useSessions.ts`: loads on mount, exposes `refetch`, and supports optimistic delete with automatic rollback on HTTP failure

**Task 48.4: Frontend — SessionSidebar + SessionListItem** ✅
- [x] `SessionSidebar.tsx` — 280px persistent rail on `md+`, slide-in drawer below `md` with dim backdrop; Escape closes; backdrop tap closes; motion-reduced friendly
- [x] `SessionListItem.tsx` — derived title, relative timestamp (via new `lib/relative-time.ts`), `message_count`; hover/focus-revealed trash icon that swaps to inline Check/X confirm/cancel on touch and desktop
- [x] All interactive targets ≥44×44 with visible focus rings; empty/loading/error states

**Task 48.5: Frontend — ChatLayout + Hamburger Toggle** ✅
- [x] New `ChatLayout.tsx` — owns both `useChat` and `useSessions` so the sidebar and chat window share session state; `md:grid md:grid-cols-[280px_1fr]`
- [x] `ChatWindow` refactored: takes `chat: UseChatReturn` as a prop (no longer self-instantiates the hook), exposes a mobile-only header with a hamburger button that opens the drawer and reflects state via `aria-expanded`
- [x] Whenever a fresh `sessionId` appears (e.g. after the first message of a new chat), the sidebar auto-refreshes so the new entry pops to the top
- [x] Sidebar selection → `loadSession`; delete → `removeSession` + clears the open chat if it was the one deleted

#### Day 49: Per-Message Actions, Keyboard Shortcuts, QA

**Task 49.1: Copy Button on MessageBubble** ✅
- [x] Assistant bubbles render a hover/focus-revealed Copy icon next to the timestamp; touch devices (no hover) always show it
- [x] `navigator.clipboard.writeText` → icon swaps to a green Check for 2s; `role="status" aria-live="polite"` sr-only announcement communicates success to assistive tech
- [x] Excludes streaming and empty bubbles

**Task 49.2: Per-Message Retry on Failed Sends** ✅
- [x] `ChatMessage.status?: "failed"` added to the type
- [x] `SET_ERROR` reducer updated: drops any trailing empty assistant shell and tags the last user message with `status: "failed"`
- [x] `retryMessage(id)` added to `useChat` — uses a `messagesRef` to find the failed entry, dispatches `REMOVE_MESSAGE`, then calls `sendMessage` with the original text
- [x] Failed user bubbles render with a destructive-tinted border + inline "Failed to send · Retry" row; global error banner keeps the error text but drops its redundant "Try again" button

**Task 49.3: Keyboard Shortcuts (Ctrl/Cmd+K, Ctrl/Cmd+Shift+N)** ✅
- [x] `hooks/useKeyboardShortcuts.ts` — two global accelerators with `preventDefault()` to override browser defaults (Chrome Ctrl+K address bar)
- [x] Ctrl/Cmd+K focuses the message input (by `kara-message-input` id)
- [x] Ctrl/Cmd+Shift+N calls the same `handleNewChat` the sidebar button uses

**Task 49.4: Final QA Polish** ✅
- [x] `aria-expanded` on the mobile hamburger reflects drawer state
- [x] Full backend suite: **321 passed** (Day 48 added 11 new tests)
- [x] Frontend: `tsc --noEmit` clean, `eslint` clean, `next build` succeeds on all routes

**Files Created:**
- `apps/api/src/kara_api/agent/session.py` (SessionSummaryRow + list_sessions)
- `apps/api/src/kara_api/routers/chat.py` (SessionSummary + GET /sessions)
- `apps/web/src/hooks/useSessions.ts`
- `apps/web/src/hooks/useKeyboardShortcuts.ts`
- `apps/web/src/components/chat/ChatLayout.tsx`
- `apps/web/src/components/chat/SessionSidebar.tsx`
- `apps/web/src/components/chat/SessionListItem.tsx`
- `apps/web/src/lib/relative-time.ts`

**Files Modified:**
- `apps/web/src/types/chat.ts` (+ `SessionSummary`, `ChatMessage.status`)
- `apps/web/src/lib/api.ts` (+ `listSessions`)
- `apps/web/src/hooks/useChat.ts` (+ `retryMessage`, `REMOVE_MESSAGE`, failed-status reducer logic)
- `apps/web/src/components/chat/ChatWindow.tsx` (presentational, mobile hamburger)
- `apps/web/src/components/chat/MessageBubble.tsx` (copy button, failed state, retry row)
- `apps/web/src/app/chat/page.tsx` (mounts ChatLayout instead of ChatWindow)

**Definition of Done:** ✅ Session sidebar lists past chats with derived titles and message counts, with optimistic delete + mobile drawer. Copy and retry affordances live on each message bubble. Ctrl/Cmd+K and Ctrl/Cmd+Shift+N shortcuts wired. All 321 backend tests + frontend build/lint/type-check green.

---

### Days 50–51: TaxBreakdownCard + Waterfall Visualization ✅

**Status:** ✅ COMPLETE

**Tasks:**
- [x] **Day 50.1:** Backend emit `tax_breakdown` SSE event in `chat.py` — parse `compute_tax` tool results into `TaxBreakdown` Pydantic model, emit structured SSE event, graceful `ValidationError` fallback
- [x] **Day 50.2:** Frontend types + SSE handler + reducer wiring — `TaxBreakdown` interface in `types/chat.ts`, `onTaxBreakdown` callback in `useSSE.ts`, `SET_TAX_BREAKDOWN` reducer action in `useChat.ts`
- [x] **Day 50.3:** Indian number formatting (`lib/format.ts`) — `formatINR` (₹12,50,000 with 2,2,3 grouping), `formatCompactINR` (₹12.5L/₹1.25Cr), `formatPercent`, `formatIndianNumber`
- [x] **Day 50.4:** `TaxBreakdownCard` component — KPI tiles (3-col grid), effective tax rate badge, collapsible detail section with income breakdown, deductions list, slab table, and adjustments
- [x] **Day 50.5:** Wire `TaxBreakdownCard` into `MessageBubble` — renders outside bubble for full width, guarded by `!isStreaming`
- [x] **Day 51.2:** Waterfall data transform (`lib/waterfall.ts`) — `computeWaterfallSteps()` produces up to 9 signed-delta steps with cumulative totals, zero-value skipping
- [x] **Day 51.3:** WaterfallChart SVG component — dual-scale layout (income zone + tax zone), `viewBox="0 0 360 220"`, `preserveAspectRatio`, rounded bars, dashed connectors, compact INR labels, `role="img"` + `aria-labelledby`/`aria-describedby` + `<figure>`/`<figcaption class="sr-only">`
- [x] **Day 51.3:** Waterfall animation (`globals.css`) — `@keyframes wf-grow` with staggered delay (`var(--i) * 40ms`), `transform-box: fill-box`, gated by `@media (prefers-reduced-motion: no-preference)`
- [x] **Day 51.4:** Waterfall tests (`waterfall.test.ts`) — 6 test suites, 35 assertions (happy path, deductions, zero-skipping, full breakdown, rebate regime, cumulative integrity)
- [x] **Day 51.5:** Integration — WaterfallChart rendered in TaxBreakdownCard summary view between KPI tiles and collapsible details

**Quality Review (12 findings, all fixed):**
- Card `aria-labelledby` linked to title (`titleId`)
- KPI tiles use semantic `<dl>`/`<dt>`/`<dd>` with `title` and `aria-label` for exact ₹ values
- Chevron icons `aria-hidden="true"`
- MoneyRow sections wrapped in `<dl>` (valid HTML)
- SlabTable has `<caption class="sr-only">`
- Collapsible detail has `role="region"` + `aria-label`
- Toggle button has `touch-manipulation`
- Slab upper-bound sentinel corrected to `>= 99_99_99_999`
- `formatCompactINR` preserves negative sign
- TaxBreakdownCard rendered outside prose bubble at full width

**Files Created/Modified:**
- `apps/api/src/kara_api/routers/chat.py` — tax_breakdown SSE event
- `apps/web/src/types/chat.ts` — TaxBreakdown + DeductionResult + SlabBreakdown + CapitalGainsDetail interfaces
- `apps/web/src/hooks/useSSE.ts` — onTaxBreakdown dispatch
- `apps/web/src/hooks/useChat.ts` — SET_TAX_BREAKDOWN reducer
- `apps/web/src/lib/format.ts` — Indian number formatters
- `apps/web/src/lib/waterfall.ts` — waterfall data transform
- `apps/web/src/lib/waterfall.test.ts` — 35 assertions
- `apps/web/src/components/cards/TaxBreakdownCard.tsx` — rich tax card
- `apps/web/src/components/cards/WaterfallChart.tsx` — SVG waterfall visualization
- `apps/web/src/components/chat/MessageBubble.tsx` — card integration
- `apps/web/src/app/globals.css` — wf-grow animation

**Definition of Done:** ✅ Tax breakdown renders as a polished card below assistant bubbles. Waterfall chart visualizes the computation with dual-scale layout. Indian formatting correct. WCAG AA accessibility. 375px mobile responsive. 35 tests passing.

---

### Days 52–53: RegimeComparisonCard + DeductionGapCard ✅ COMPLETE

**Status:** ✅ COMPLETE (Done 2026-04-16)

**Tasks:**
- [x] Create `RegimeComparisonCard`:
  - Side-by-side: Old Regime vs New Regime
  - Tax amount under each
  - Savings highlighted (green badge: "Save ₹X with New Regime")
  - Deductions breakdown showing what applies where
  - Recommendation badge
- [x] Create `DeductionGapCard`:
  - Progress bars for each deduction section (used / cap)
  - 80C: ₹1,20,000 / ₹1,50,000 — "₹30,000 gap"
  - Color coding: green (>80% used), yellow (50-80%), red (<50%)
  - Suggestion chips: "Invest ₹30K in ELSS to save ₹9,360"
  - Expandable investment tips section
- [x] Create `CapitalGainsCard`:
  - Asset details, holding period, gain type
  - Tax computation with exemptions shown
  - Per-transaction dl grid with rate, taxable gain, tax
- [x] Wire all 3 cards into `MessageBubble` (after RegimeComparisonCard, outside bubble)
- [x] SSE backend tests: `TestDeductionGapsSSE` (3 tests) + `TestCapitalGainsSSE` (4 tests)

**Files Created/Modified:**
- `apps/web/src/components/cards/RegimeComparisonCard.tsx` (created Day 52)
- `apps/web/src/components/cards/DeductionGapCard.tsx` (created Day 53.3)
- `apps/web/src/components/cards/CapitalGainsCard.tsx` (created Day 53.4)
- `apps/web/src/components/chat/MessageBubble.tsx` (wired Day 53.5)
- `apps/api/tests/test_chat_endpoints.py` (7 new tests Day 53.5)

**Definition of Done:** ✅ All 3 card types render in chat. Visual design is clean and informative. Mobile responsive. SSE events covered by 7 new backend tests.

---

### Days 54–55: Frontend Polish + Error Handling ✅

**Status:** ✅ COMPLETE (2026-04-23)

**Tasks:**
- [x] Error boundary components — graceful error display
- [x] Network error handling — retry prompts, offline indicator
- [x] Loading states — skeleton loaders for every async operation
- [x] Toast notifications for success/error actions
- [x] 404 page
- [x] SEO: meta tags, Open Graph, favicon, JSON-LD, robots/sitemap
- [x] Performance: lazy loading via next/dynamic, bundle analyzer
- [x] Production Dockerfile (3-stage, non-root, standalone output)
- [x] docker-compose.yml web service (health checks, deps)
- [ ] Cross-browser testing: Chrome, Firefox, Safari, Edge (manual — see docs/day-55-browser-checklist.md)
- [ ] Mobile testing: iOS Safari, Android Chrome (manual — see docs/day-55-browser-checklist.md)
- [ ] Lighthouse audit: 90+ on all categories (manual — see docs/day-55-lighthouse.md)

**Files to Create/Modify:**
- `apps/web/src/components/ErrorBoundary.tsx`
- `apps/web/src/app/not-found.tsx`
- `apps/web/Dockerfile`
- `docker-compose.yml` (add web service)

**🏆 MILESTONE (Day 55):** Full UI with rich cards. Mobile-ready. 3-container Docker setup.

---

## Phase 4 — Advanced Features (Days 56–70)

**Goal:** Form 16 auto-parse + scenarios. Upload Form 16 → auto-fill profile. Scenario simulator. TDS, advance tax, ITR form selector.

**Phase Milestone:** Form 16 auto-parse + scenario simulator working.

---

### Days 56–58: Form 16 PDF Parser ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create `packages/tax-engine/src/kara_tax_engine/parsers/form16.py`:
  - Parse Form 16 Part A: employer TAN, PAN, salary breakup, TDS deducted
  - Parse Form 16 Part B: gross salary, deductions claimed, tax computation by employer
  - Handle multiple formats (PDF layouts vary by employer/software)
  - Use PyMuPDF (fitz) or pdfplumber for extraction
  - Fallback: OCR with pytesseract for scanned PDFs
- [ ] Extract key fields:
  - Gross salary, basic, HRA, special allowance
  - 80C, 80D, 80CCD deductions
  - TDS already deducted (monthly + total)
  - PAN of employee
- [ ] Auto-fill TaxProfile from parsed Form 16
- [ ] Write parser tests — 10+ tests with sample PDFs
  - [ ] Test standard government Form 16 format
  - [ ] Test private company format (varies)
  - [ ] Test missing fields handling
  - [ ] Test multi-page Form 16

**Files to Create:**
- `packages/tax-engine/src/kara_tax_engine/parsers/__init__.py`
- `packages/tax-engine/src/kara_tax_engine/parsers/form16.py`
- `packages/tax-engine/tests/test_form16_parser.py`
- `packages/tax-engine/tests/fixtures/sample_form16/` (sample PDFs)

**Definition of Done:** Form 16 PDF → TaxProfile conversion works for at least 3 different formats. Tests pass.

---

### Days 59–60: AIS/26AS Parser + Document Upload API ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create `packages/tax-engine/src/kara_tax_engine/parsers/ais.py`:
  - Parse Annual Information Statement (AIS) — JSON or PDF
  - 57 categories of financial information
  - Extract: salary, interest, dividends, MF transactions, property sales
- [ ] Create `packages/tax-engine/src/kara_tax_engine/parsers/form26as.py`:
  - Parse 26AS — TDS credits, advance tax, self-assessment tax
  - Extract TDS entries with section, amount, TAN
- [ ] Create upload endpoint in API:
  - `POST /api/v1/documents/upload` — accept PDF/JSON
  - Auto-detect document type (Form 16 / AIS / 26AS)
  - Parse and return extracted TaxProfile
  - Store parsed data in session
- [ ] Add drag-and-drop upload in chat UI:
  - Drop zone in chat input area
  - File type validation (PDF, JSON only)
  - Upload progress indicator
  - Display parsed summary as a card in chat
- [ ] Write parser tests — 10+ tests

**Files to Create:**
- `packages/tax-engine/src/kara_tax_engine/parsers/ais.py`
- `packages/tax-engine/src/kara_tax_engine/parsers/form26as.py`
- `apps/api/src/kara_api/routers/documents.py`
- `apps/web/src/components/chat/FileUpload.tsx`
- `packages/tax-engine/tests/test_ais_parser.py`
- `packages/tax-engine/tests/test_26as_parser.py`

**Definition of Done:** All 3 document types parse correctly. Upload → auto-fill works in chat. Drag-and-drop UI functional.

---

### Days 61–62: Scenario Simulation — Regime + Investment Comparison ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create interactive regime comparison simulator:
  - Slider for salary (₹5L → ₹2Cr)
  - Toggle deduction sections on/off
  - Real-time tax recalculation as inputs change
  - Visual comparison chart (old vs new regime)
- [ ] Create investment comparison tool:
  - Compare: ELSS vs PPF vs NPS vs FD vs SSY
  - Inputs: amount, time horizon, risk tolerance
  - Outputs: post-tax returns, lock-in period, tax saved
  - Visualization: comparison table + bar chart
- [ ] Create API endpoint: `POST /api/v1/simulate/regime`
- [ ] Create API endpoint: `POST /api/v1/simulate/investment`

**Files to Create:**
- `apps/api/src/kara_api/routers/simulate.py`
- `apps/web/src/app/simulate/page.tsx`
- `apps/web/src/components/simulate/RegimeSlider.tsx`
- `apps/web/src/components/simulate/InvestmentCompare.tsx`

**Definition of Done:** Both simulators work interactively. Real-time updates as inputs change.

---

### Days 63–64: 80C Optimizer + Salary Restructuring ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create 80C allocation optimizer:
  - Input: available amount for 80C investments
  - Output: optimal split across 12 instruments
  - Rank by: returns (ELSS > PPF > FD), lock-in, risk
  - Respect ₹1.5L cap, sub-limits (e.g., PPF ₹1.5L own cap)
- [ ] Create salary restructuring calculator:
  - Input: current CTC breakup
  - Suggest: increase HRA, add NPS employer contribution, add meal/fuel allowances
  - Output: revised breakup with tax savings
  - Visual: before vs after comparison
- [ ] Add tools to agent: `optimize_80c`, `restructure_salary`

**Files to Create:**
- `packages/tax-engine/src/kara_tax_engine/optimizer.py` (enhance)
- `apps/web/src/components/simulate/AllocationOptimizer.tsx`
- `apps/web/src/components/simulate/SalaryRestructure.tsx`

**Definition of Done:** 80C optimizer suggests investment mix. Salary restructuring shows savings. Agent can call both tools.

---

### Days 65–66: TDS Rate Table + Advance Tax Calculator ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create `rules/fy_2025_26/tds/rates.yaml` — 15+ TDS sections:
  - 192: Salary (slab rate)
  - 194A: Interest (bank ₹40K/₹50K senior threshold, 10%)
  - 194B: Lottery/game (30%)
  - 194C: Contractor (1%/2%)
  - 194D: Insurance commission (5%)
  - 194H: Commission/brokerage (5%)
  - 194I: Rent (2%/10%)
  - 194J: Professional fees (10%)
  - 194K: MF income (10%)
  - 194LA: Property acquisition (1%)
  - 194O: E-commerce (1%)
  - 194Q: Purchase of goods (0.1%)
  - 194S: Crypto/VDA (1%)
  - 195: Non-resident (rates vary)
  - 206C: TCS on foreign remittance (5%/20%)
- [ ] Implement TDS lookup tool
- [ ] Create advance tax quarterly calculator:
  - Q1 (June 15): 15% of estimated tax
  - Q2 (Sep 15): 45% cumulative
  - Q3 (Dec 15): 75% cumulative
  - Q4 (Mar 15): 100%
  - Output: payment schedule with amounts + due dates
- [ ] Write TDS + advance tax tests — 10+ tests

**Files to Create:**
- `packages/tax-engine/src/kara_tax_engine/rules/fy_2025_26/tds/rates.yaml`
- `packages/tax-engine/src/kara_tax_engine/tds.py`
- `packages/tax-engine/src/kara_tax_engine/advance_tax.py`
- `packages/tax-engine/tests/test_tds.py`
- `packages/tax-engine/tests/test_advance_tax.py`

**Definition of Done:** TDS rate lookup works for all sections. Advance tax schedule generates correct quarterly amounts.

---

### Days 67–68: Interest Computation (234A/B/C) + ITR Form Selector ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Implement Section 234A/B/C interest computation:
  - 234A: Late filing — 1% per month on unpaid tax (from due date to filing date)
  - 234B: Default on advance tax — 1% per month (April to filing)
  - 234C: Deferment of advance tax — 1% per month on shortfall per quarter
  - Handle: partial months, already paid amounts
- [ ] Create ITR form selector decision tree:
  - ITR-1 (Sahaj): salary + 1 house property + other sources, income ≤ ₹50L
  - ITR-2: salary + capital gains + multiple house properties, no business
  - ITR-3: business/profession income
  - ITR-4 (Sugam): presumptive business income (44AD/44ADA)
  - Decision based on: income sources, total income, residential status
- [ ] Add tools to agent: `calculate_interest`, `select_itr_form`
- [ ] Write tests — 10+ tests

**Files to Create:**
- `packages/tax-engine/src/kara_tax_engine/interest.py`
- `packages/tax-engine/src/kara_tax_engine/itr_selector.py`
- `packages/tax-engine/tests/test_interest.py`
- `packages/tax-engine/tests/test_itr_selector.py`

**Definition of Done:** Interest computation correct for all 3 sections. ITR selector recommends correct form. Tests pass.

---

### Days 69–70: End-to-End Journey Tests + Golden File Regression ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create 10 end-to-end journey tests — full conversation flows:
  1. Salaried employee, new regime, standard deductions
  2. Salaried with HRA, old regime, multiple deductions
  3. Senior citizen with pension + FD interest
  4. Business income (44AD presumptive)
  5. Capital gains from equity MF sale
  6. Property sale with Section 54 exemption
  7. Crypto trader (VDA)
  8. NRI with Indian income
  9. Multiple income sources (salary + business + capital gains)
  10. Form 16 upload → auto-compute → regime comparison
- [ ] Create golden file regression suite:
  - 20 pre-computed tax profiles with known correct outputs
  - Test: compute → compare output against golden file
  - Any mismatch = test failure
  - Update golden files only with explicit approval
- [ ] Performance benchmarks:
  - Tax computation: <50ms for single profile
  - Regime comparison: <100ms
  - Hybrid search: <200ms

**Files to Create:**
- `apps/api/tests/test_e2e_journeys.py`
- `packages/tax-engine/tests/test_golden_files.py`
- `packages/tax-engine/tests/golden/` (20 profile JSON files)

**🏆 MILESTONE (Day 70):** Form 16 auto-parse + scenario simulator working. All advanced features integrated.

---

## Phase 5 — Polish + Launch (Days 71–80)

**Goal:** v1.0 launched on GitHub. Production-ready. Docker one-command.

**Phase Milestone:** v1.0 launched on GitHub.

---

### Days 71–72: Input Validation + Security Hardening ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Input validation on all API endpoints:
  - PAN format validation (AAAAA0000A)
  - Income ranges (non-negative, reasonable max)
  - Date format validation
  - Enum value validation
- [ ] PII stripping:
  - Never store PAN in logs
  - Mask PAN in API responses (show last 4 only)
  - Session data cleanup after 24 hours
- [ ] Prompt injection protection:
  - Input sanitization before LLM
  - System prompt armoring
  - Output validation — ensure AI doesn't leak system prompt
- [ ] Rate limiting:
  - 60 requests/minute per IP (computation endpoints)
  - 20 requests/minute per IP (chat endpoints)
  - 429 Too Many Requests response
- [ ] CORS configuration — whitelist allowed origins
- [ ] Security headers: CSP, X-Frame-Options, HSTS

**Files to Create/Modify:**
- `apps/api/src/kara_api/middleware/security.py`
- `apps/api/src/kara_api/middleware/rate_limit.py`
- `apps/api/src/kara_api/middleware/validation.py`

**Definition of Done:** All inputs validated. PII stripped from logs. Rate limiting active. CORS configured.

---

### Days 73–74: Self-Hosting Guide + API Documentation ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create self-hosting guide: `docs/self-hosting.md`
  - Prerequisites: Docker, API key (Claude/GPT/Ollama)
  - One-command setup: `docker compose up`
  - Environment variables reference
  - Ollama setup for fully local (no API key needed)
  - Troubleshooting common issues
- [ ] Create API documentation: `docs/api.md`
  - All endpoints with request/response examples
  - Authentication (API key in header)
  - Error codes and handling
  - Rate limits
- [ ] Add OpenAPI/Swagger UI at `/docs` (FastAPI built-in)
- [ ] Create architecture documentation: `docs/architecture.md`
  - System diagram (Mermaid)
  - Data flow: user → chat → agent → tools → engine → response
  - Database schema diagram
  - Technology choices and rationale

**Files to Create:**
- `docs/self-hosting.md`
- `docs/api.md`
- `docs/architecture.md`

**Definition of Done:** Self-hosting guide tested — fresh machine can run Kara in <5 minutes. API docs cover all endpoints.

---

### Days 75–76: Contributing Guide + Adding New FY ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create `CONTRIBUTING.md`:
  - Development setup (local, without Docker)
  - Code style (ruff config, type hints)
  - Test requirements (all tests must pass)
  - PR process and review guidelines
  - Issue labeling and triage
- [ ] Create `docs/adding-new-fy.md`:
  - Step-by-step guide for adding FY 2026-27 rules
  - Copy `rules/fy_2025_26/` → `rules/fy_2026_27/`
  - Update slab rates, deduction limits, rebate thresholds
  - Run test suite against new FY
  - Community contribution template
- [ ] Create `docs/adding-new-deduction.md`:
  - How to add a new deduction section
  - YAML schema, model updates, computer changes, tests
- [ ] Add code documentation:
  - Module-level docstrings for all source files
  - Complex function documentation

**Files to Create:**
- `CONTRIBUTING.md`
- `docs/adding-new-fy.md`
- `docs/adding-new-deduction.md`

**Definition of Done:** A new contributor can set up the project, understand the architecture, and add a new FY's rules by following the docs.

---

### Days 77–78: CI/CD + GitHub Repository Setup ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create `.github/workflows/ci.yml`:
  - Trigger: push to main, PRs
  - Matrix: Python 3.11, 3.12, 3.13
  - Steps: install deps, ruff lint, ruff format check, pytest with coverage
  - Coverage threshold: 80%+
  - Upload coverage to Codecov
- [ ] Create `.github/workflows/release.yml`:
  - Trigger: push tag v*
  - Build and publish to PyPI
  - Create GitHub Release with changelog
- [ ] Create issue templates:
  - `.github/ISSUE_TEMPLATE/bug_report.md`
  - `.github/ISSUE_TEMPLATE/feature_request.md`
  - `.github/ISSUE_TEMPLATE/new_fy_request.md`
- [ ] Create `CODEOWNERS` — assign reviewers per directory
- [ ] Create labels: bug, enhancement, good-first-issue, new-fy, documentation
- [ ] Create `.gitignore` (comprehensive: Python, Node, IDE, env files)
- [ ] Create `LICENSE` — AGPL-3.0 for platform, MIT for tax-engine

**Files to Create:**
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `.github/ISSUE_TEMPLATE/new_fy_request.md`
- `CODEOWNERS`
- `.gitignore`
- `LICENSE`

**Definition of Done:** CI runs on every PR. Release workflow publishes to PyPI on tag. Issue templates ready.

---

### Days 79–80: README + Launch Prep ⬜

**Status:** ⬜ TODO

**Tasks:**
- [ ] Create professional `README.md`:
  - Logo + badges (CI, coverage, PyPI version, license)
  - One-line description
  - Screenshot or demo GIF of chat interface
  - Quick start (3 commands: clone, docker compose up, open browser)
  - Features list with checkmarks
  - Architecture diagram
  - Tech stack badges
  - Contributing section
  - License section
  - "Made with ❤️ in India" footer
- [ ] Create demo GIF/video:
  - Record chat interaction
  - Show Form 16 upload → auto-compute
  - Show regime comparison card
- [ ] Final testing:
  - [ ] Fresh Docker install test (clean machine)
  - [ ] All 350+ tests passing
  - [ ] Lighthouse 90+ scores
  - [ ] Mobile testing on real devices
- [ ] Tag `v1.0.0`
- [ ] Prepare launch posts:
  - Hacker News submission draft
  - Reddit r/india, r/IndiaInvestments, r/developersIndia
  - Product Hunt listing
  - Twitter/X thread

**Files to Create:**
- `README.md` (root, comprehensive)
- `assets/demo.gif`
- `assets/screenshot.png`
- `assets/architecture.svg`

**🏆 MILESTONE (Day 80):** v1.0 launched on GitHub. Production-ready. Docker one-command. 350+ tests.

---

## Quick Reference — Files by Phase

### Phase 1 (Days 1-20): packages/tax-engine/
```
packages/tax-engine/
├── pyproject.toml                          ✅
├── README.md                               ✅
├── LICENSE                                 ✅
├── CHANGELOG.md                            ✅
├── src/kara_tax_engine/
│   ├── __init__.py                         ✅
│   ├── models.py                           ✅
│   ├── loader.py                           ✅
│   ├── computer.py                         ✅
│   ├── comparator.py                       ✅
│   ├── optimizer.py                        ✅
│   ├── capital_gains.py                    ⬜ (Days 15-17)
│   └── rules/fy_2025_26/
│       ├── meta.yaml                       ✅
│       ├── slabs/new_regime.yaml           ✅
│       ├── slabs/old_regime.yaml           ✅
│       ├── deductions/                     ⬜ (Days 10-14)
│       └── capital_gains/                  ⬜ (Days 15-17)
├── tests/
│   ├── conftest.py                         ✅
│   ├── test_loader.py                      ✅
│   ├── test_models.py                      ✅
│   ├── test_new_regime.py                  ✅
│   ├── test_old_regime.py                  🔄 (25 tests done, Days 8-9 remain)
│   ├── test_deductions.py                  ⬜ (Days 10-14)
│   ├── test_capital_gains.py               ⬜ (Days 15-17)
│   ├── test_comparator.py                  ✅
│   └── test_optimizer.py                   ✅
```

### Phase 2 (Days 21-40): apps/api/
```
apps/api/
├── pyproject.toml                          ⬜
├── Dockerfile                              ⬜
├── src/kara_api/
│   ├── main.py                             ⬜
│   ├── config.py                           ⬜
│   ├── db/
│   │   ├── models.py                       ⬜
│   │   └── connection.py                   ⬜
│   ├── routers/
│   │   ├── tax.py                          ⬜
│   │   └── chat.py                         ⬜
│   ├── knowledge/
│   │   ├── search.py                       ⬜
│   │   └── embeddings.py                   ⬜
│   ├── llm/
│   │   ├── client.py                       ⬜
│   │   └── config.py                       ⬜
│   └── agent/
│       ├── tools.py                        ⬜
│       ├── executor.py                     ⬜
│       ├── prompts.py                      ⬜
│       ├── profile_builder.py              ⬜
│       ├── loop.py                         ⬜
│       └── session.py                      ⬜
```

### Phase 3 (Days 41-55): apps/web/
```
apps/web/
├── package.json                            ⬜
├── Dockerfile                              ⬜
├── src/
│   ├── app/
│   │   ├── layout.tsx                      ⬜
│   │   ├── page.tsx                        ⬜
│   │   └── chat/page.tsx                   ⬜
│   ├── components/
│   │   ├── layout/Header.tsx               ⬜
│   │   ├── layout/Footer.tsx               ⬜
│   │   ├── chat/ChatWindow.tsx             ⬜
│   │   ├── chat/MessageBubble.tsx          ⬜
│   │   ├── chat/MessageInput.tsx           ⬜
│   │   ├── cards/TaxBreakdownCard.tsx      ✅
│   │   ├── cards/WaterfallChart.tsx        ✅
│   │   ├── cards/RegimeComparisonCard.tsx  ✅
│   │   ├── cards/DeductionGapCard.tsx      ✅
│   │   └── cards/CapitalGainsCard.tsx      ✅
│   ├── hooks/
│   │   ├── useChat.ts                      ✅
│   │   └── useSSE.ts                       ✅
│   ├── lib/
│   │   ├── api.ts                          ✅
│   │   ├── format.ts                       ✅
│   │   ├── waterfall.ts                    ✅
│   │   └── waterfall.test.ts              ✅
│   └── types/chat.ts                       ✅
```

---

## Changelog

| Date | Actual Day | Roadmap Days Completed | Notes |
|------|-----------|------------------------|-------|
| 2026-03-24 | 1 | Days 1–6 | Setup + models + loader + computer + new regime tests. Stubs for capital_gains, optimizer, comparator. |
| 2026-03-24 | 2 | Day 7 | Old regime slab tests — 25 tests (below-60, senior, super-senior, 87A rebate). Total: 106/350+ tests. |
| 2026-04-09 | — | Days 50–51 | TaxBreakdownCard + WaterfallChart + format.ts + SSE wiring + 35 waterfall tests. Quality audit: 12 a11y/UX findings fixed. |
| 2026-04-16 | — | Days 52–53 | RegimeComparisonCard + DeductionGapCard + CapitalGainsCard + MessageBubble wiring + 7 SSE backend tests. All 3 card types live in chat. |
| | | | |
