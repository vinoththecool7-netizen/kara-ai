"""Tests for Section 80C deductions and regime filtering (FY 2025-26).

Covers the 80C/80CCC/80CCD(1) combined cap (₹1,50,000), 80CCD(1B)
additional NPS (₹50,000), 80CCD(2) employer NPS (both regimes),
regime filtering, and end-to-end tax savings.

Old regime slabs (below 60):
  ₹0-2.5L: 0% | ₹2.5-5L: 5% | ₹5-10L: 20% | ₹10L+: 30%
Standard deduction: ₹50,000 (old) / ₹75,000 (new).
Cess: 4% on (tax + surcharge).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Group A: Basic 80C Application (5 tests)
# ---------------------------------------------------------------------------


def test_80c_basic_150k_deduction(computer):
    """80C=150K on 10L old regime. taxable=8L, total_deductions=150000, tax=75400.

    Gross 10L - 50K std = 9.5L GTI. Less 80C 1.5L = 8L taxable.
    Slabs: 2.5L@0% + 2.5L@5%(12500) + 3L@20%(60000) = 72,500.
    Cess: ceil(72500 * 0.04) = 2,900. Total: 75,400.
    """
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 150_000})
    assert r.taxable_income == 800_000
    assert r.total_deductions == 150_000
    assert r.total_tax_payable == 75_400


def test_80c_reduces_taxable_income(computer):
    """80C=100K on 10L old regime reduces taxable to 850K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 100_000})
    assert r.taxable_income == 850_000


def test_80c_deduction_appears_in_results(computer):
    """Verify DeductionResult entry for 80C with section, allowed, cap."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 150_000})
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 150_000
    assert entry.cap == 150_000


def test_80c_zero_claim_no_deduction_entry(computer):
    """80C=0 under old regime produces no deduction entry."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 0})
    assert r.total_deductions == 0
    sections = [d.section for d in r.deductions_applied]
    assert "80C/80CCC/80CCD(1)" not in sections


def test_80c_no_deductions_means_zero(computer):
    """No deductions dict at all results in zero total_deductions."""
    r = computer.compute(gross_salary=1_000_000, regime="old")
    assert r.total_deductions == 0


# ---------------------------------------------------------------------------
# Group B: Cap Enforcement (5 tests)
# ---------------------------------------------------------------------------


def test_80c_cap_at_150k(computer):
    """80C=200K is capped to 150K. claimed=200000, allowed=150000."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 200_000})
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.claimed == 200_000
    assert entry.allowed == 150_000
    assert entry.cap == 150_000


def test_80c_partial_claim_50k(computer):
    """80C=50K. allowed=50000, taxable=900000."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 50_000})
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 50_000
    assert r.taxable_income == 900_000


def test_80c_claim_1_rupee(computer):
    """80C=1. allowed=1, total_deductions=1."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 1})
    assert r.total_deductions == 1
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 1


def test_80c_exact_cap_claim(computer):
    """80C=150K exactly equals cap. allowed=150000."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80C": 150_000})
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 150_000


def test_80c_very_large_claim(computer):
    """80C=1000000 is capped to 150000."""
    r = computer.compute(gross_salary=2_000_000, regime="old", deductions={"80C": 1_000_000})
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 150_000


# ---------------------------------------------------------------------------
# Group C: Combined Cap 80C+80CCC+80CCD(1) (6 tests)
# ---------------------------------------------------------------------------


def test_combined_80c_80ccc_within_cap(computer):
    """80C=100K + 80CCC=30K = 130K, within 150K cap. allowed=130000."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 100_000, "80CCC": 30_000},
    )
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 130_000


def test_combined_80c_80ccd1_within_cap(computer):
    """80C=100K + 80CCD1=40K = 140K, within 150K cap. allowed=140000."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 100_000, "80CCD1": 40_000},
    )
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 140_000


def test_combined_all_three_at_cap(computer):
    """80C=100K + 80CCC=25K + 80CCD1=25K = 150K exactly. allowed=150000."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 100_000, "80CCC": 25_000, "80CCD1": 25_000},
    )
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 150_000


def test_combined_exceeds_cap(computer):
    """80C=100K + 80CCC=50K + 80CCD1=50K = 200K total, capped to 150000."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 100_000, "80CCC": 50_000, "80CCD1": 50_000},
    )
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.claimed == 200_000
    assert entry.allowed == 150_000


def test_combined_all_three_zero(computer):
    """All three sub-sections at zero produces no 80C entry."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 0, "80CCC": 0, "80CCD1": 0},
    )
    sections = [d.section for d in r.deductions_applied]
    assert "80C/80CCC/80CCD(1)" not in sections


def test_combined_only_80ccc(computer):
    """Only 80CCC=120K, no 80C or 80CCD1. allowed=120000 under combined section."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80CCC": 120_000},
    )
    entry = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    assert entry.allowed == 120_000


# ---------------------------------------------------------------------------
# Group D: Regime Filtering (6 tests)
# ---------------------------------------------------------------------------


def test_80c_rejected_in_new_regime(computer):
    """New regime rejects 80C. 10L gross, 80C=150K, total_deductions=0."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80C": 150_000})
    assert r.total_deductions == 0
    sections = [d.section for d in r.deductions_applied]
    assert "80C/80CCC/80CCD(1)" not in sections


def test_80ccc_rejected_in_new_regime(computer):
    """New regime rejects 80CCC. total_deductions=0."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80CCC": 50_000})
    assert r.total_deductions == 0


def test_80ccd1_rejected_in_new_regime(computer):
    """New regime rejects 80CCD1. total_deductions=0."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80CCD1": 50_000})
    assert r.total_deductions == 0


def test_80ccd1b_rejected_in_new_regime(computer):
    """New regime rejects 80CCD(1B). total_deductions=0."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80CCD1B": 50_000})
    assert r.total_deductions == 0


def test_80ccd2_allowed_in_new_regime(computer):
    """80CCD(2) employer NPS is allowed in new regime. 10L, 80CCD2=100K.

    GTI = 10L - 75K std = 9.25L. Deductions = 100K. Taxable = 8.25L.
    total_deductions=100000.
    """
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80CCD2": 100_000})
    assert r.total_deductions == 100_000
    entry = next(d for d in r.deductions_applied if d.section == "80CCD(2)")
    assert entry.allowed == 100_000


def test_80ccd2_allowed_in_old_regime(computer):
    """80CCD(2) employer NPS is also allowed in old regime. allowed=100000."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80CCD2": 100_000})
    entry = next(d for d in r.deductions_applied if d.section == "80CCD(2)")
    assert entry.allowed == 100_000


# ---------------------------------------------------------------------------
# Group E: 80CCD(1B) Additional NPS (3 tests)
# ---------------------------------------------------------------------------


def test_80ccd1b_additional_50k(computer):
    """80C=150K + 80CCD1B=50K in old regime. Two separate entries, total=200K.

    Combined 80C entry: allowed=150K. Separate 80CCD(1B): allowed=50K.
    """
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 150_000, "80CCD1B": 50_000},
    )
    entry_80c = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    entry_1b = next(d for d in r.deductions_applied if d.section == "80CCD(1B)")
    assert entry_80c.allowed == 150_000
    assert entry_1b.allowed == 50_000
    assert r.total_deductions == 200_000


def test_80ccd1b_capped_at_50k(computer):
    """80CCD1B=80K is capped at 50K. claimed=80000, allowed=50000, cap=50000."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80CCD1B": 80_000},
    )
    entry = next(d for d in r.deductions_applied if d.section == "80CCD(1B)")
    assert entry.claimed == 80_000
    assert entry.allowed == 50_000
    assert entry.cap == 50_000


def test_80ccd1b_with_full_80c_stack(computer):
    """Full stack: 80C=100K + 80CCC=25K + 80CCD1=25K + 80CCD1B=50K.

    Combined 80C/80CCC/80CCD(1) = 150K (capped). Plus 80CCD(1B) = 50K.
    Total = 200K.
    """
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80C": 100_000, "80CCC": 25_000, "80CCD1": 25_000, "80CCD1B": 50_000},
    )
    entry_80c = next(d for d in r.deductions_applied if d.section == "80C/80CCC/80CCD(1)")
    entry_1b = next(d for d in r.deductions_applied if d.section == "80CCD(1B)")
    assert entry_80c.allowed == 150_000
    assert entry_1b.allowed == 50_000
    assert r.total_deductions == 200_000


# ---------------------------------------------------------------------------
# Group F: End-to-End Tax Savings (3 tests)
# ---------------------------------------------------------------------------


def test_80c_saves_tax_at_30pct_bracket(computer):
    """20L gross, old regime. 80C=150K saves ₹46,800.

    Without: taxable=19.5L. Slab: 250K@0% + 250K@5%(12500) + 500K@20%(100000)
      + 950K@30%(285000) = 397,500. Cess: 15,900. Total: 413,400.
    With 80C=150K: taxable=18L. Slab: 250K@0% + 250K@5%(12500) + 500K@20%(100000)
      + 800K@30%(240000) = 352,500. Cess: 14,100. Total: 366,600.
    Saving: 413,400 - 366,600 = 46,800.
    """
    r_without = computer.compute(gross_salary=2_000_000, regime="old")
    r_with = computer.compute(gross_salary=2_000_000, regime="old", deductions={"80C": 150_000})
    assert r_without.total_tax_payable == 413_400
    assert r_with.total_tax_payable == 366_600
    assert r_without.total_tax_payable - r_with.total_tax_payable == 46_800


def test_80c_saves_tax_at_20pct_bracket(computer):
    """8L gross, old regime. 80C=150K saves ₹31,200.

    Without: taxable=7.5L. Slab: 250K@0% + 250K@5%(12500) + 250K@20%(50000)
      = 62,500. Cess: 2,500. Total: 65,000.
    With 80C=150K: taxable=6L. Slab: 250K@0% + 250K@5%(12500) + 100K@20%(20000)
      = 32,500. Cess: 1,300. Total: 33,800.
    Saving: 65,000 - 33,800 = 31,200.
    """
    r_without = computer.compute(gross_salary=800_000, regime="old")
    r_with = computer.compute(gross_salary=800_000, regime="old", deductions={"80C": 150_000})
    assert r_without.total_tax_payable == 65_000
    assert r_with.total_tax_payable == 33_800
    assert r_without.total_tax_payable - r_with.total_tax_payable == 31_200


def test_full_deduction_stack_old_regime(computer):
    """15L gross, 80C=150K + 80CCD1B=50K + 80CCD2=80K. total_deductions=280K.

    GTI = 15L - 50K std = 14.5L. Total deductions: 150K + 50K + 80K = 280K.
    Taxable = 14,50,000 - 2,80,000 = 11,70,000.
    """
    r = computer.compute(
        gross_salary=1_500_000,
        regime="old",
        deductions={"80C": 150_000, "80CCD1B": 50_000, "80CCD2": 80_000},
    )
    assert r.total_deductions == 280_000
    assert r.taxable_income == 1_170_000
