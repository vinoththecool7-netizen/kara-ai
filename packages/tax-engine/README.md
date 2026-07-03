# kara-tax-engine

Deterministic Indian income tax computation engine for FY 2025-26 (AY 2026-27).

Compute tax in 3 lines of Python. No infrastructure needed.

## Features

- **8-step tax pipeline** -- income aggregation, deductions, slab tax, capital gains, surcharge, cess, Section 87A rebate, net tax
- **Both regimes** -- New regime (7 slabs) and old regime (age-variant slabs)
- **Full deductions engine** -- 80C, 80CCC, 80CCD, 80D, 80E, 80G, 80TTA/TTB, 80U/DD, 24(b), HRA
- **Capital gains** -- Equity, debt MF, property, gold, crypto/VDA with STCG/LTCG, grandfathering, loss set-off
- **Regime comparator** -- Side-by-side comparison with breakeven analysis
- **Deduction optimizer** -- Finds tax-saving gaps, suggests ELSS/PPF/NPS/health insurance
- **YAML-driven rules** -- Extensible to future financial years
- **390+ tests** -- Comprehensive coverage at every boundary

## Installation

```bash
pip install kara-tax-engine
```

## Quick Start

### Compute Tax

```python
from kara_tax_engine import TaxComputer

computer = TaxComputer(fy="2025-26")
result = computer.compute(gross_salary=1_500_000, regime="new")

print(f"Tax: {result.total_tax_payable:,}")       # Tax: 97,500
print(f"Rate: {result.effective_tax_rate}%")       # Rate: 6.84%
```

### Full Profile with Deductions

```python
from kara_tax_engine import TaxComputer, TaxProfile, Deductions, Regime

computer = TaxComputer(fy="2025-26")
profile = TaxProfile(
    gross_salary=2_000_000,
    regime=Regime.OLD,
    deductions=Deductions(
        section_80c=150_000,
        section_80d=25_000,
        section_80ccd_1b=50_000,
    ),
)
result = computer.compute_from_profile(profile)
print(f"Taxable income: {result.taxable_income:,}")
print(f"Tax payable: {result.total_tax_payable:,}")
```

### Compare Regimes

```python
from kara_tax_engine import RegimeComparator, TaxProfile, Deductions

comparator = RegimeComparator(fy="2025-26")
profile = TaxProfile(
    gross_salary=1_500_000,
    deductions=Deductions(section_80c=150_000, section_80d=25_000),
)
comparison = comparator.compare(profile)

print(f"Recommended: {comparison.recommended_regime.value}")
print(f"Savings: {comparison.savings:,}")
print(comparison.explanation)
```

### Optimize Deductions

```python
from kara_tax_engine import DeductionOptimizer, TaxProfile, Deductions, Regime

optimizer = DeductionOptimizer(fy="2025-26")
profile = TaxProfile(
    gross_salary=1_500_000,
    regime=Regime.OLD,
    deductions=Deductions(section_80c=80_000),
)
result = optimizer.optimize(profile)

print(f"Current tax: {result.current_tax:,}")
print(f"Optimized tax: {result.optimized_tax:,}")
print(f"Potential saving: {result.total_potential_saving:,}")
for s in result.suggestions:
    print(f"  {s.section} - {s.instrument}: {s.suggested_amount:,} (saves {s.potential_tax_saving:,})")
```

### Capital Gains

```python
from kara_tax_engine import CapitalGainsCalculator

cg = CapitalGainsCalculator(fy="2025-26")
result = cg.compute(
    asset_class="listed_equity",
    purchase_price=500_000,
    sale_price=800_000,
    holding_months=18,
)
print(f"{result.gain_type.value}: {result.taxable_gain:,} @ {result.tax_rate}%")
```

## Supported Tax Sections

| Section | Description | Regime | Cap |
|---------|-------------|--------|-----|
| 80C/80CCC/80CCD(1) | Investments (EPF, PPF, ELSS, etc.) | Old only | 1,50,000 combined |
| 80CCD(1B) | Additional NPS | Old only | 50,000 |
| 80CCD(2) | Employer NPS | Both | No fixed cap |
| 80D | Health insurance | Old only | 25K/50K self + 50K parents |
| 80E | Education loan interest | Old only | No cap |
| 80G | Donations | Old only | Actual amount |
| 80TTA/80TTB | Savings interest | Old only | 10K / 50K (senior) |
| 80U/80DD | Disability | Old only | 75K / 1,25,000 |
| 24(b) | Home loan interest | Old only | 2,00,000 |
| 10(13A) | HRA exemption | Old only | Computed |

## API Reference

### TaxComputer

```python
computer = TaxComputer(fy="2025-26")
result = computer.compute(gross_salary=..., regime="new"|"old", ...)
result = computer.compute_from_profile(profile: TaxProfile)
```

Returns `TaxBreakdown` with full audit trail (`computation_steps`).

### RegimeComparator

```python
comparator = RegimeComparator(fy="2025-26")
comparison = comparator.compare(profile: TaxProfile)
```

Returns `RegimeComparison` with both breakdowns, recommended regime, savings, and breakeven analysis.

### DeductionOptimizer

```python
optimizer = DeductionOptimizer(fy="2025-26")
result = optimizer.optimize(profile: TaxProfile)
```

Returns `OptimizationResult` with ranked suggestions and potential tax savings.

### CapitalGainsCalculator

```python
cg = CapitalGainsCalculator(fy="2025-26")
result = cg.compute(asset_class=..., purchase_price=..., sale_price=..., holding_months=...)
results = cg.compute_multiple(transactions=[...])
```

Supports: `listed_equity`, `equity_mf`, `debt_mf`, `property`, `gold`, `unlisted_shares`, `vda_crypto`.

## Supported Financial Years

- **FY 2025-26** (AY 2026-27) -- fully supported

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/
```

## License

MIT
