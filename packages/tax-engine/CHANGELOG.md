# Changelog

## v0.1.0 (2026-03-26)

### Added

- Core tax computation engine (`TaxComputer`) with 8-step deterministic pipeline
- New regime support: 7 slabs (0% to 30%), standard deduction 75K
- Old regime support: age-variant slabs (below-60, senior 60-80, super-senior 80+)
- Full deductions engine: 80C/80CCC/80CCD, 80D, 80E, 80G, 80TTA/TTB, 80U/DD, 24(b), HRA
- Capital gains calculator: equity, debt MF, property, gold, unlisted shares, crypto/VDA
- Grandfathering for pre-31-Jan-2018 equity (FMV adjustment)
- Loss set-off rules with 8-year carry forward
- Section 87A rebate with marginal relief (new and old regime)
- Surcharge tiers with marginal relief (10%/15%/25%/37%)
- Health & Education Cess at 4%
- Regime comparator with breakeven deduction analysis
- Deduction optimizer with investment suggestions (ELSS, PPF, NPS, health insurance)
- YAML-driven rule system for FY 2025-26 (extensible to future years)
- 306+ comprehensive tests covering all boundaries and edge cases
