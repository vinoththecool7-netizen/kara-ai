"""Tests for the new regime (FY 2025-26) computation pipeline.

All tests use TaxComputer.compute(gross_salary=X, regime="new") unless otherwise noted.
Standard deduction: ₹75,000. Taxable income = gross_salary - 75,000.

Slab structure:
  ₹0–4L: 0%  |  ₹4–8L: 5%  |  ₹8–12L: 10%  |  ₹12–16L: 15%
  ₹16–20L: 20%  |  ₹20–24L: 25%  |  ₹24L+: 30%

Section 87A rebate: full rebate if taxable ≤ ₹12L (max rebate ₹60,000).
Marginal relief: just above ₹12L, tax capped at (taxable - 12L).
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Group A: Zero and low income (5 tests)
# ---------------------------------------------------------------------------


def test_zero_income(computer):
    r = computer.compute(gross_salary=0, regime="new")
    assert r.total_tax_payable == 0


def test_below_standard_deduction(computer):
    """50K gross → taxable = 0 (below 75K std deduction)."""
    r = computer.compute(gross_salary=50_000, regime="new")
    assert r.taxable_income == 0
    assert r.total_tax_payable == 0


def test_exactly_standard_deduction(computer):
    """75K gross → taxable = 0 exactly."""
    r = computer.compute(gross_salary=75_000, regime="new")
    assert r.taxable_income == 0
    assert r.total_tax_payable == 0


def test_income_in_zero_pct_slab(computer):
    """400K gross → taxable = 325K, entirely in 0% slab."""
    r = computer.compute(gross_salary=400_000, regime="new")
    assert r.taxable_income == 325_000
    assert r.total_tax_payable == 0


def test_income_fills_zero_pct_slab_exactly(computer):
    """475K gross → taxable = 400K. Fills first slab exactly, tax = 0."""
    r = computer.compute(gross_salary=475_000, regime="new")
    assert r.taxable_income == 400_000
    assert r.total_tax_payable == 0


# ---------------------------------------------------------------------------
# Group B: Section 87A rebate zone — taxable ≤ 12L (8 tests)
# ---------------------------------------------------------------------------


def test_rebate_500k(computer):
    """500K gross → taxable = 425K. Tax before rebate = 1,250. Rebate wipes it."""
    r = computer.compute(gross_salary=500_000, regime="new")
    assert r.taxable_income == 425_000
    assert r.rebate_87a > 0
    assert r.total_tax_payable == 0


def test_rebate_875k(computer):
    """875K gross → taxable = 800K. Tax before rebate = 20,000. Rebate applies."""
    r = computer.compute(gross_salary=875_000, regime="new")
    assert r.taxable_income == 800_000
    assert r.total_tax_payable == 0


def test_rebate_1m(computer):
    """1,000K gross → taxable = 925K. Tax before rebate = 32,500. Rebate applies."""
    r = computer.compute(gross_salary=1_000_000, regime="new")
    assert r.taxable_income == 925_000
    assert r.total_tax_payable == 0


def test_rebate_exact_boundary(computer):
    """1,275K gross → taxable = 1,200K exactly. Max rebate = 60K. Cess (2,400) is not covered."""
    r = computer.compute(gross_salary=1_275_000, regime="new")
    assert r.taxable_income == 1_200_000
    assert r.rebate_87a == 60_000
    assert r.total_tax_payable == 2_400  # cess = ceil(60000 * 0.04) = 2400, rebate doesn't cover it


def test_marginal_relief_1_rupee_above_boundary(computer):
    """1,275,001 gross → taxable = 1,200,001. Tax capped at excess = 1."""
    r = computer.compute(gross_salary=1_275_001, regime="new")
    assert r.taxable_income == 1_200_001
    assert r.total_tax_payable == 1
    assert r.marginal_relief_87a > 0


def test_marginal_relief_50k_above_boundary(computer):
    """1,325K gross → taxable = 1,250K. Tax capped at excess (50K) over 12L."""
    r = computer.compute(gross_salary=1_325_000, regime="new")
    assert r.taxable_income == 1_250_000
    assert r.total_tax_payable == 50_000


def test_above_rebate_zone_no_relief(computer):
    """1,375K gross → taxable = 1,300K. Excess = 100K. Tax = 78K < 100K, no marginal relief."""
    r = computer.compute(gross_salary=1_375_000, regime="new")
    assert r.taxable_income == 1_300_000
    assert r.total_tax_payable == 78_000
    assert r.marginal_relief_87a == 0
    assert r.rebate_87a == 0


def test_150k_taxable_no_rebate(computer):
    """1,500K gross → taxable = 1,425K. No rebate, no marginal relief."""
    r = computer.compute(gross_salary=1_500_000, regime="new")
    assert r.taxable_income == 1_425_000
    assert r.rebate_87a == 0
    assert r.total_tax_payable == 97_500


# ---------------------------------------------------------------------------
# Group C: Mid-income slab boundaries (8 tests)
# ---------------------------------------------------------------------------


def test_slab_boundary_16L(computer):
    """1,675K gross → taxable = 1,600K. Tax = 0+20K+40K+60K = 120K. Cess = 4,800."""
    r = computer.compute(gross_salary=1_675_000, regime="new")
    assert r.taxable_income == 1_600_000
    assert r.tax_on_normal_income == 120_000
    assert r.total_tax_payable == 124_800


def test_income_1800k(computer):
    """1,800K gross → taxable = 1,725K. 120K + 125K*0.20 = 145K. Cess = 5,800."""
    r = computer.compute(gross_salary=1_800_000, regime="new")
    assert r.taxable_income == 1_725_000
    assert r.tax_on_normal_income == 145_000
    assert r.total_tax_payable == 150_800


def test_slab_boundary_20L(computer):
    """2,075K gross → taxable = 2,000K. Tax = 200K. Cess = 8,000."""
    r = computer.compute(gross_salary=2_075_000, regime="new")
    assert r.taxable_income == 2_000_000
    assert r.tax_on_normal_income == 200_000
    assert r.total_tax_payable == 208_000


def test_income_2200k(computer):
    """2,200K gross → taxable = 2,125K. 200K + 125K*0.25 = 231,250. Cess = 9,250."""
    r = computer.compute(gross_salary=2_200_000, regime="new")
    assert r.taxable_income == 2_125_000
    assert r.tax_on_normal_income == 231_250
    assert r.total_tax_payable == 240_500


def test_slab_boundary_24L(computer):
    """2,475K gross → taxable = 2,400K. Tax = 300K. Cess = 12,000."""
    r = computer.compute(gross_salary=2_475_000, regime="new")
    assert r.taxable_income == 2_400_000
    assert r.tax_on_normal_income == 300_000
    assert r.total_tax_payable == 312_000


def test_income_2700k(computer):
    """2,700K gross → taxable = 2,625K. 300K + 225K*0.30 = 367,500. Cess = 14,700."""
    r = computer.compute(gross_salary=2_700_000, regime="new")
    assert r.taxable_income == 2_625_000
    assert r.tax_on_normal_income == 367_500
    assert r.total_tax_payable == 382_200


def test_income_3075k(computer):
    """3,075K gross → taxable = 3,000K. 300K + 600K*0.30 = 480K. Cess = 19,200."""
    r = computer.compute(gross_salary=3_075_000, regime="new")
    assert r.taxable_income == 3_000_000
    assert r.tax_on_normal_income == 480_000
    assert r.total_tax_payable == 499_200


def test_income_5m(computer):
    """5,000K gross → taxable = 4,925K. No surcharge (taxable < 50L). Cess = 4%."""
    r = computer.compute(gross_salary=5_000_000, regime="new")
    assert r.surcharge_amount == 0
    assert r.total_tax_payable == r.tax_on_normal_income + r.cess_amount


# ---------------------------------------------------------------------------
# Group D: Standard deduction (3 tests)
# ---------------------------------------------------------------------------


def test_standard_deduction_applied(computer):
    r = computer.compute(gross_salary=1_500_000, regime="new")
    assert r.standard_deduction == 75_000
    assert r.net_salary == 1_425_000


def test_standard_deduction_zero_for_non_salary(computer):
    """No standard deduction when there is no salary income."""
    r = computer.compute(gross_salary=0, regime="new", other_income=500_000)
    assert r.standard_deduction == 0


def test_net_salary_equals_gross_minus_std_ded(computer):
    r = computer.compute(gross_salary=2_000_000, regime="new")
    assert r.net_salary == r.gross_salary - r.standard_deduction


# ---------------------------------------------------------------------------
# Group E: Surcharge (7 tests)
# ---------------------------------------------------------------------------


def test_no_surcharge_below_50L(computer):
    """Taxable = 50L exactly. Threshold is >, not >=. No surcharge."""
    r = computer.compute(gross_salary=5_075_000, regime="new")
    assert r.taxable_income == 5_000_000
    assert r.surcharge_amount == 0
    assert r.surcharge_rate == 0.0


def test_surcharge_10pct_just_above_50L(computer):
    r = computer.compute(gross_salary=5_100_000, regime="new")
    assert r.taxable_income == 5_025_000
    assert r.surcharge_rate == 0.10
    assert r.surcharge_amount > 0


def test_surcharge_10pct_marginal_relief_applies(computer):
    """Just above 50L surcharge threshold — marginal relief should kick in."""
    r = computer.compute(gross_salary=5_100_000, regime="new")
    assert r.marginal_relief_surcharge > 0


def test_surcharge_15pct_above_1cr(computer):
    r = computer.compute(gross_salary=10_100_000, regime="new")
    assert r.surcharge_rate == 0.15
    assert r.surcharge_amount > 0


def test_surcharge_25pct_above_2cr(computer):
    r = computer.compute(gross_salary=20_100_000, regime="new")
    assert r.surcharge_rate == 0.25


def test_surcharge_capped_at_25pct_new_regime(computer):
    """New regime caps surcharge at 25% even for very high income (6 Cr)."""
    r = computer.compute(gross_salary=60_000_000, regime="new")
    assert r.surcharge_rate == 0.25


def test_surcharge_total_tax(computer):
    """For 6Cr, computed total should match the known value."""
    r = computer.compute(gross_salary=60_000_000, regime="new")
    assert r.total_tax_payable == 22_824_750


# ---------------------------------------------------------------------------
# Group F: Slab breakdown audit trail (4 tests)
# ---------------------------------------------------------------------------


def test_slab_breakdown_count_all_7(computer):
    """Income spanning all slabs → 7 slab entries."""
    r = computer.compute(gross_salary=3_000_000, regime="new")
    assert len(r.slab_breakdown) == 7


def test_slab_breakdown_rates(computer):
    r = computer.compute(gross_salary=3_000_000, regime="new")
    rates = [s.rate for s in r.slab_breakdown]
    assert rates == [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]


def test_slab_breakdown_taxable_at_exact_boundary(computer):
    """Taxable = 2,400K fills slabs 1-6 exactly (each 400K wide), slab 7 is 0."""
    r = computer.compute(gross_salary=2_475_000, regime="new")
    assert r.taxable_income == 2_400_000
    for slab in r.slab_breakdown[:6]:
        assert slab.taxable_in_slab == 400_000


def test_computation_steps_not_empty(computer):
    r = computer.compute(gross_salary=1_500_000, regime="new")
    assert len(r.computation_steps) > 0


# ---------------------------------------------------------------------------
# Group G: Other income heads (4 tests)
# ---------------------------------------------------------------------------


def test_other_income_added_to_gti(computer):
    r = computer.compute(gross_salary=1_000_000, regime="new", other_income=200_000)
    # GTI = net_salary + other_income = (1000000-75000) + 200000 = 1125000
    assert r.gross_total_income == 1_125_000


def test_business_income_no_standard_deduction(computer):
    """Business income with zero salary → standard deduction should NOT apply."""
    r = computer.compute(gross_salary=0, regime="new", business_income=1_000_000)
    assert r.standard_deduction == 0
    assert r.gross_total_income == 1_000_000


def test_house_property_loss_capped_at_2L(computer):
    """HP loss of -3L is capped at -2L set-off."""
    r = computer.compute(gross_salary=2_000_000, regime="new", house_property_income=-300_000)
    # GTI = (2000000-75000) + (-200000) = 1725000
    assert r.gross_total_income == 1_725_000


def test_house_property_loss_within_2L(computer):
    """HP loss of -1L is fully set off."""
    r = computer.compute(gross_salary=2_000_000, regime="new", house_property_income=-100_000)
    # GTI = (2000000-75000) + (-100000) = 1825000
    assert r.gross_total_income == 1_825_000


# ---------------------------------------------------------------------------
# Group H: Cess (2 tests)
# ---------------------------------------------------------------------------


def test_cess_rate(computer):
    r = computer.compute(gross_salary=1_500_000, regime="new")
    assert r.cess_rate == 0.04


def test_cess_amount_calculation(computer):
    r = computer.compute(gross_salary=1_500_000, regime="new")
    tax_plus_surcharge = r.total_tax_before_surcharge + r.surcharge_amount
    expected_cess = math.ceil(tax_plus_surcharge * 0.04)
    assert r.cess_amount == expected_cess


# ---------------------------------------------------------------------------
# Group I: Effective tax rate (2 tests)
# ---------------------------------------------------------------------------


def test_effective_tax_rate_zero_income(computer):
    r = computer.compute(gross_salary=0, regime="new")
    assert r.effective_tax_rate == 0.0


def test_effective_tax_rate_formula(computer):
    r = computer.compute(gross_salary=1_500_000, regime="new")
    expected = round(r.total_tax_payable / r.gross_total_income * 100, 2)
    assert r.effective_tax_rate == expected
