# Adding a new financial year (e.g. FY 2026-27)

Tax rules are data, not code. Adding a year is a YAML change plus tests —
if you find yourself editing Python, something is wrong (and
`tests/test_yaml_driven_caps.py` will probably fail you anyway).

## Steps

1. **Copy the rule pack**

   ```bash
   cd packages/tax-engine/src/kara_tax_engine/rules
   cp -r fy_2025_26 fy_2026_27
   ```

2. **Update every file against the new Finance Act**

   | File | What lives there |
   |---|---|
   | `meta.yaml` | Cess rate, standard deductions, filing dates |
   | `slabs/new_regime.yaml` | Slabs, §87A rebate, surcharge tiers |
   | `slabs/old_regime.yaml` | Age-variant slabs, rebate, surcharge |
   | `deductions/*.yaml` | Every cap: 80C combined, 80CCD(1B), 80D by age, 80TTA/TTB, 80U/DD, 24(b), HRA percentages |
   | `capital_gains/*.yaml` | Rates, holding periods, exemptions per asset class |
   | `tds/rates.yaml` | TDS sections, rates, thresholds |

   Cite the Finance Act / CBDT notification for each change in your PR.

3. **Point tests at the new year**

   - Add boundary tests for anything that changed (slab edges, rebate
     threshold, new caps), mirroring `tests/test_new_regime.py` patterns.
   - Build a golden set: copy `tests/golden/profiles.py`, regenerate
     expectations with the new FY, and review every number by hand.

4. **Run everything**

   ```bash
   cd packages/tax-engine && pytest
   ```

5. **Make it reachable**

   The API currently instantiates engines with `fy="2025-26"`
   (`apps/api/src/kara_api/tools/executor.py`). Making the FY selectable
   per-request is tracked as follow-up work; until then, bump the default
   there and in `TaxProfile.financial_year` / `assessment_year` defaults.

## Sanity checklist

- [ ] ₹12L-equivalent rebate boundary returns ₹0 under the new regime rules
- [ ] Surcharge marginal relief verified at each threshold
- [ ] Golden file diffs reviewed line by line
- [ ] No Python file changed except (temporarily) the default FY string
