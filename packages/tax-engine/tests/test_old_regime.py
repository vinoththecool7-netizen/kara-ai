"""Tests for the old regime (FY 2025-26) computation pipeline.

All tests use TaxComputer.compute(gross_salary=X, regime="old", age_category=Y).
Standard deduction: ₹50,000 (old regime).  Taxable income = gross_salary - 50,000.

Slab structures:
  Below 60:     ₹0–2.5L: 0%  |  ₹2.5–5L: 5%  |  ₹5–10L: 20%  |  ₹10L+: 30%
  Senior 60–80: ₹0–3L: 0%    |  ₹3–5L: 5%    |  ₹5–10L: 20%  |  ₹10L+: 30%
  Super 80+:    ₹0–5L: 0%    |  ₹5–10L: 20%  |  ₹10L+: 30%

Section 87A rebate: ₹12,500 if taxable income ≤ ₹5L (no marginal relief in old regime).
Surcharge: 10% @50L, 15% @1Cr, 25% @2Cr, 37% @5Cr.
Cess: 4% on (tax + surcharge).

Note: The 87A rebate is applied against income-tax BEFORE cess; cess is then
levied on the post-rebate amount (per the Finance Act computation order).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Group A: Below-60 — Zero and low income (5 tests)
# ---------------------------------------------------------------------------


def test_old_zero_income(computer):
    """Zero gross → zero tax."""
    r = computer.compute(gross_salary=0, regime="old")
    assert r.total_tax_payable == 0


def test_old_below_std_deduction(computer):
    """30K gross → taxable = 0 (below 50K std deduction)."""
    r = computer.compute(gross_salary=30_000, regime="old")
    assert r.taxable_income == 0
    assert r.total_tax_payable == 0


def test_old_in_zero_slab(computer):
    """250K gross → taxable = 200K, entirely in 0% slab."""
    r = computer.compute(gross_salary=250_000, regime="old")
    assert r.taxable_income == 200_000
    assert r.total_tax_payable == 0


def test_old_fills_zero_slab(computer):
    """300K gross → taxable = 250K, fills 0% slab exactly."""
    r = computer.compute(gross_salary=300_000, regime="old")
    assert r.taxable_income == 250_000
    assert r.total_tax_payable == 0


def test_old_5pct_slab_with_rebate(computer):
    """400K gross → taxable = 350K, slab tax = 5000, but rebate zeroes it out."""
    r = computer.compute(gross_salary=400_000, regime="old")
    assert r.taxable_income == 350_000
    assert r.tax_on_normal_income == 5_000  # 100K @ 5%
    assert r.total_tax_payable == 0  # rebate covers tax + cess


# ---------------------------------------------------------------------------
# Group B: Below-60 — Mid and high income (5 tests)
# ---------------------------------------------------------------------------


def test_old_20pct_slab(computer):
    """800K gross → taxable = 750K.

    Slabs: 250K@0% + 250K@5%(12500) + 250K@20%(50000) = 62,500.
    Cess: ceil(62500 * 0.04) = 2,500. Total: 65,000.
    """
    r = computer.compute(gross_salary=800_000, regime="old")
    assert r.taxable_income == 750_000
    assert r.tax_on_normal_income == 62_500
    assert r.cess_amount == 2_500
    assert r.total_tax_payable == 65_000


def test_old_30pct_slab(computer):
    """15L gross → taxable = 14.5L.

    Slabs: 250K@0% + 250K@5%(12500) + 500K@20%(100000) + 450K@30%(135000) = 247,500.
    Cess: ceil(247500 * 0.04) = 9,900. Total: 257,400.
    """
    r = computer.compute(gross_salary=1_500_000, regime="old")
    assert r.taxable_income == 1_450_000
    assert r.tax_on_normal_income == 247_500
    assert r.cess_amount == 9_900
    assert r.total_tax_payable == 257_400


def test_old_std_deduction_is_50k(computer):
    """Old regime standard deduction is ₹50,000 (not ₹75,000 like new regime)."""
    r = computer.compute(gross_salary=800_000, regime="old")
    assert r.standard_deduction == 50_000
    assert r.net_salary == 750_000


def test_old_no_std_deduction_for_business(computer):
    """Business income only → no standard deduction.

    Taxable = 800K. Slabs: 250K@0% + 250K@5%(12500) + 300K@20%(60000) = 72,500.
    Cess: ceil(72500 * 0.04) = 2,900. Total: 75,400.
    """
    r = computer.compute(gross_salary=0, business_income=800_000, regime="old")
    assert r.standard_deduction == 0
    assert r.taxable_income == 800_000
    assert r.tax_on_normal_income == 72_500
    assert r.total_tax_payable == 75_400


def test_old_exact_boundary_10L(computer):
    """1050K gross → taxable = 1,000K, fills 20% slab exactly.

    Slabs: 250K@0% + 250K@5%(12500) + 500K@20%(100000) = 112,500.
    Cess: ceil(112500 * 0.04) = 4,500. Total: 117,000.
    """
    r = computer.compute(gross_salary=1_050_000, regime="old")
    assert r.taxable_income == 1_000_000
    assert r.tax_on_normal_income == 112_500
    assert r.total_tax_payable == 117_000


# ---------------------------------------------------------------------------
# Group C: Senior citizen (60–80) slabs (5 tests)
# ---------------------------------------------------------------------------


def test_senior_zero_slab(computer):
    """Senior, 350K gross → taxable = 300K, all in senior 0% slab (threshold ₹3L)."""
    r = computer.compute(gross_salary=350_000, regime="old", age_category="senior")
    assert r.taxable_income == 300_000
    assert r.tax_on_normal_income == 0
    assert r.total_tax_payable == 0


def test_senior_5pct_with_rebate(computer):
    """Senior, 450K gross → taxable = 400K, slab = 5000, rebate covers it."""
    r = computer.compute(gross_salary=450_000, regime="old", age_category="senior")
    assert r.taxable_income == 400_000
    assert r.tax_on_normal_income == 5_000  # 100K @ 5% (300K-400K)
    assert r.total_tax_payable == 0  # rebate covers tax + cess


def test_senior_20pct_slab(computer):
    """Senior, 800K gross → taxable = 750K.

    Slabs: 300K@0% + 200K@5%(10000) + 250K@20%(50000) = 60,000.
    Cess: ceil(60000 * 0.04) = 2,400. Total: 62,400.
    """
    r = computer.compute(gross_salary=800_000, regime="old", age_category="senior")
    assert r.taxable_income == 750_000
    assert r.tax_on_normal_income == 60_000
    assert r.cess_amount == 2_400
    assert r.total_tax_payable == 62_400


def test_senior_30pct_slab(computer):
    """Senior, 15L gross → taxable = 14.5L.

    Slabs: 300K@0% + 200K@5%(10000) + 500K@20%(100000) + 450K@30%(135000) = 245,000.
    Cess: ceil(245000 * 0.04) = 9,800. Total: 254,800.
    """
    r = computer.compute(gross_salary=1_500_000, regime="old", age_category="senior")
    assert r.taxable_income == 1_450_000
    assert r.tax_on_normal_income == 245_000
    assert r.cess_amount == 9_800
    assert r.total_tax_payable == 254_800


def test_senior_std_deduction_50k(computer):
    """Seniors also get ₹50,000 standard deduction in old regime."""
    r = computer.compute(gross_salary=800_000, regime="old", age_category="senior")
    assert r.standard_deduction == 50_000


# ---------------------------------------------------------------------------
# Group D: Super-senior citizen (80+) slabs (4 tests)
# ---------------------------------------------------------------------------


def test_super_senior_zero_slab_5L(computer):
    """Super-senior, 550K gross → taxable = 500K, all in 0% slab (threshold ₹5L)."""
    r = computer.compute(gross_salary=550_000, regime="old", age_category="super_senior")
    assert r.taxable_income == 500_000
    assert r.tax_on_normal_income == 0
    assert r.total_tax_payable == 0


def test_super_senior_20pct_slab(computer):
    """Super-senior, 800K gross → taxable = 750K.

    Slabs: 500K@0% + 250K@20%(50000) = 50,000.
    Cess: ceil(50000 * 0.04) = 2,000. Total: 52,000.
    """
    r = computer.compute(gross_salary=800_000, regime="old", age_category="super_senior")
    assert r.taxable_income == 750_000
    assert r.tax_on_normal_income == 50_000
    assert r.cess_amount == 2_000
    assert r.total_tax_payable == 52_000


def test_super_senior_30pct_slab(computer):
    """Super-senior, 15L gross → taxable = 14.5L.

    Slabs: 500K@0% + 500K@20%(100000) + 450K@30%(135000) = 235,000.
    Cess: ceil(235000 * 0.04) = 9,400. Total: 244,400.
    """
    r = computer.compute(gross_salary=1_500_000, regime="old", age_category="super_senior")
    assert r.taxable_income == 1_450_000
    assert r.tax_on_normal_income == 235_000
    assert r.cess_amount == 9_400
    assert r.total_tax_payable == 244_400


def test_super_senior_higher_exemption_than_below60(computer):
    """At same income, super-senior pays less due to higher 0% threshold.

    Below-60 at 750K taxable: slab = 250K@0% + 250K@5% + 250K@20% = 62,500.
    Super-senior at 750K taxable: slab = 500K@0% + 250K@20% = 50,000.
    Difference: ₹12,500 in slab tax alone.
    """
    r_below = computer.compute(gross_salary=800_000, regime="old", age_category="below_60")
    r_super = computer.compute(gross_salary=800_000, regime="old", age_category="super_senior")
    assert r_below.tax_on_normal_income == 62_500
    assert r_super.tax_on_normal_income == 50_000
    assert r_below.total_tax_payable > r_super.total_tax_payable


# ---------------------------------------------------------------------------
# Group E: Section 87A rebate — old regime (5 tests)
# ---------------------------------------------------------------------------


def test_old_rebate_full_below_5L(computer):
    """Taxable = 450K (well below 5L). Rebate covers everything → tax = 0.

    Slab: 250K@0% + 200K@5% = 10,000. Rebate = min(10000, 12500) = 10,000.
    Cess on post-rebate tax (0) = 0. Net: 0.
    """
    r = computer.compute(gross_salary=500_000, regime="old")
    assert r.taxable_income == 450_000
    assert r.tax_on_normal_income == 10_000
    assert r.rebate_87a == r.tax_on_normal_income + r.cess_amount  # full rebate
    assert r.total_tax_payable == 0


def test_old_rebate_at_5L_boundary(computer):
    """Taxable = exactly 500K. Slab = 12,500, fully rebated (cap 12,500).

    Cess applies on post-rebate tax (zero) → total payable 0.
    """
    r = computer.compute(gross_salary=550_000, regime="old")
    assert r.taxable_income == 500_000
    assert r.tax_on_normal_income == 12_500
    assert r.rebate_87a == 12_500
    assert r.cess_amount == 0
    assert r.total_tax_payable == 0


def test_old_no_rebate_above_5L(computer):
    """Taxable = 550K (above 5L threshold). No rebate at all.

    Slab: 250K@0% + 250K@5%(12500) + 50K@20%(10000) = 22,500.
    Cess: ceil(22500 * 0.04) = 900. Total: 23,400.
    """
    r = computer.compute(gross_salary=600_000, regime="old")
    assert r.taxable_income == 550_000
    assert r.rebate_87a == 0
    assert r.total_tax_payable == 23_400


def test_old_rebate_max_is_12500(computer):
    """Verify rebate is capped at ₹12,500 under old regime."""
    r = computer.compute(gross_salary=550_000, regime="old")  # taxable = 500K
    assert r.rebate_87a <= 12_500


def test_senior_rebate_applies(computer):
    """Seniors also get 87A rebate if taxable ≤ 5L.

    Senior, gross=530K → taxable = 480K. Slab: 300K@0% + 180K@5% = 9,000.
    Cess: ceil(9000 * 0.04) = 360. Total before: 9,360.
    Rebate = min(9360, 12500) = 9,360. Net: 0.
    """
    r = computer.compute(gross_salary=530_000, regime="old", age_category="senior")
    assert r.taxable_income == 480_000
    assert r.tax_on_normal_income == 9_000
    assert r.total_tax_payable == 0


# ---------------------------------------------------------------------------
# Group F: Slab breakdown audit trail (1 test)
# ---------------------------------------------------------------------------


def test_old_slab_breakdown_count(computer):
    """Below-60 at 14.5L taxable → 4 slabs in breakdown."""
    r = computer.compute(gross_salary=1_500_000, regime="old")
    assert len(r.slab_breakdown) == 4
    rates = [s.rate for s in r.slab_breakdown]
    assert rates == [0.0, 0.05, 0.20, 0.30]


# ---------------------------------------------------------------------------
# Group G: Surcharge tiers — 10% / 15% / 25% / 37% (6 tests)
# ---------------------------------------------------------------------------


def test_old_no_surcharge_at_50L_boundary(computer):
    """Taxable = 50L exactly. 50L is NOT > 50L → no surcharge.

    Slab: 2.5L@0% + 2.5L@5%(12500) + 5L@20%(100000) + 40L@30%(1200000) = 13,12,500.
    Cess: ceil(1312500 * 0.04) = 52,500. Total: 13,65,000.
    """
    r = computer.compute(gross_salary=5_050_000, regime="old")
    assert r.taxable_income == 5_000_000
    assert r.tax_on_normal_income == 1_312_500
    assert r.surcharge_amount == 0
    assert r.surcharge_rate == 0.0
    assert r.cess_amount == 52_500
    assert r.total_tax_payable == 1_365_000


def test_old_surcharge_10pct_at_60L(computer):
    """Taxable = 60L → 10% surcharge (well above 50L threshold, no MR).

    Slab tax: 16,12,500. Surcharge @10%: 1,61,250.
    Tax+SC: 17,73,750. Cess: 70,950. Total: 18,44,700.
    """
    r = computer.compute(gross_salary=6_050_000, regime="old")
    assert r.taxable_income == 6_000_000
    assert r.tax_on_normal_income == 1_612_500
    assert r.surcharge_rate == 0.10
    assert r.surcharge_amount == 161_250
    assert r.marginal_relief_surcharge == 0
    assert r.cess_amount == 70_950
    assert r.total_tax_payable == 1_844_700


def test_old_surcharge_10pct_at_1Cr_boundary(computer):
    """Taxable = 1Cr exactly → still 10% (NOT > 1Cr for 15% tier).

    Slab tax: 28,12,500. Surcharge @10%: 2,81,250.
    Tax+SC: 30,93,750. Cess: 1,23,750. Total: 32,17,500.
    """
    r = computer.compute(gross_salary=10_050_000, regime="old")
    assert r.taxable_income == 10_000_000
    assert r.tax_on_normal_income == 2_812_500
    assert r.surcharge_rate == 0.10
    assert r.surcharge_amount == 281_250
    assert r.total_tax_payable == 3_217_500


def test_old_surcharge_15pct_at_1_5Cr(computer):
    """Taxable = 1.5Cr → 15% surcharge (well above 1Cr threshold).

    Slab tax: 43,12,500. Surcharge @15%: 6,46,875.
    Tax+SC: 49,59,375. Cess: 1,98,375. Total: 51,57,750.
    """
    r = computer.compute(gross_salary=15_050_000, regime="old")
    assert r.taxable_income == 15_000_000
    assert r.tax_on_normal_income == 4_312_500
    assert r.surcharge_rate == 0.15
    assert r.surcharge_amount == 646_875
    assert r.marginal_relief_surcharge == 0
    assert r.total_tax_payable == 5_157_750


def test_old_surcharge_25pct_at_3Cr(computer):
    """Taxable = 3Cr → 25% surcharge (well above 2Cr threshold).

    Slab tax: 88,12,500. Surcharge @25%: 22,03,125.
    Tax+SC: 1,10,15,625. Cess: 4,40,625. Total: 1,14,56,250.
    """
    r = computer.compute(gross_salary=30_050_000, regime="old")
    assert r.taxable_income == 30_000_000
    assert r.tax_on_normal_income == 8_812_500
    assert r.surcharge_rate == 0.25
    assert r.surcharge_amount == 2_203_125
    assert r.marginal_relief_surcharge == 0
    assert r.total_tax_payable == 11_456_250


def test_old_surcharge_37pct_at_6Cr(computer):
    """Taxable = 6Cr → 37% surcharge (old regime max, well above 5Cr).

    Slab tax: 1,78,12,500. Surcharge @37%: 65,90,625.
    Tax+SC: 2,44,03,125. Cess: 9,76,125. Total: 2,53,79,250.
    """
    r = computer.compute(gross_salary=60_050_000, regime="old")
    assert r.taxable_income == 60_000_000
    assert r.tax_on_normal_income == 17_812_500
    assert r.surcharge_rate == 0.37
    assert r.surcharge_amount == 6_590_625
    assert r.marginal_relief_surcharge == 0
    assert r.total_tax_payable == 25_379_250


# ---------------------------------------------------------------------------
# Group H: Surcharge marginal relief (3 tests)
# ---------------------------------------------------------------------------


def test_old_surcharge_mr_at_50L(computer):
    """Taxable = 50.5L (just above 50L) → 10% surcharge with marginal relief.

    Slab tax: 13,27,500. Surcharge raw @10%: 1,32,750.
    Tax at 50L threshold: 13,12,500. Excess: 50,000.
    Marginal limit: 13,62,500. MR: 97,750. Surcharge after MR: 35,000.
    Cess: 54,500. Total: 14,17,000.
    """
    r = computer.compute(gross_salary=5_100_000, regime="old")
    assert r.taxable_income == 5_050_000
    assert r.surcharge_rate == 0.10
    assert r.marginal_relief_surcharge == 97_750
    assert r.surcharge_amount == 35_000
    assert r.total_tax_payable == 1_417_000


def test_old_surcharge_mr_at_1Cr(computer):
    """Taxable = 1,00,50,000 (just above 1Cr) → 15% surcharge with MR.

    Slab tax: 28,27,500. Surcharge raw @15%: 4,24,125.
    Tax at 1Cr threshold: 28,12,500. Excess: 50,000.
    MR: 3,89,125. Surcharge after MR: 35,000.
    Cess: 1,14,500. Total: 29,77,000.
    """
    r = computer.compute(gross_salary=10_100_000, regime="old")
    assert r.taxable_income == 10_050_000
    assert r.surcharge_rate == 0.15
    assert r.marginal_relief_surcharge == 389_125
    assert r.surcharge_amount == 35_000
    assert r.total_tax_payable == 2_977_000


def test_old_surcharge_mr_at_5Cr(computer):
    """Taxable = 5,00,50,000 (just above 5Cr) → 37% surcharge with MR.

    Slab tax: 1,48,27,500. Surcharge raw @37%: 54,86,175.
    Tax at 5Cr threshold: 1,48,12,500. Excess: 50,000.
    MR: 54,51,175. Surcharge after MR: 35,000.
    Cess: 5,94,500. Total: 1,54,57,000.
    """
    r = computer.compute(gross_salary=50_100_000, regime="old")
    assert r.taxable_income == 50_050_000
    assert r.surcharge_rate == 0.37
    assert r.marginal_relief_surcharge == 5_451_175
    assert r.surcharge_amount == 35_000
    assert r.total_tax_payable == 15_457_000


def test_senior_surcharge_mr_uses_senior_slabs(computer):
    """Senior just above 50L: threshold tax must use the SENIOR slab set.

    Senior, taxable = 50,00,100. Slab tax: 10,000 + 1,00,000 + 30%×40,00,100
    = 13,10,030. Senior threshold tax at 50L = 13,10,000; excess = 100, so
    the marginal limit is 13,10,100 → surcharge after relief = 70.
    Cess: 4% of 13,10,100 = 52,404. Total: 13,62,504.

    (Using below-60 slabs for the threshold would inflate the limit to
    13,12,600 and overcharge the senior by ~₹2,500.)
    """
    r = computer.compute(gross_salary=5_050_100, regime="old", age_category="senior")
    assert r.taxable_income == 5_000_100
    assert r.tax_on_normal_income == 1_310_030
    assert r.surcharge_amount == 70
    assert r.total_tax_payable == 1_362_504


# ---------------------------------------------------------------------------
# Group I: 37% surcharge — old regime exclusive (2 tests)
# ---------------------------------------------------------------------------


def test_old_surcharge_37pct_rate_verified(computer):
    """Old regime at 6Cr: surcharge rate is 37% (not capped at 25%)."""
    r = computer.compute(gross_salary=60_050_000, regime="old")
    assert r.surcharge_rate == 0.37


def test_new_surcharge_capped_at_25pct_same_income(computer):
    """New regime at same income: surcharge capped at 25% (not 37%).

    This is the key old-regime-exclusive difference: old allows 37% surcharge
    while new regime caps at 25%.
    """
    r_old = computer.compute(gross_salary=60_050_000, regime="old")
    r_new = computer.compute(gross_salary=60_050_000, regime="new")

    assert r_old.surcharge_rate == 0.37
    assert r_new.surcharge_rate == 0.25

    # Old regime pays MORE surcharge (37% vs 25% on similar base)
    assert r_old.surcharge_amount > r_new.surcharge_amount


# ---------------------------------------------------------------------------
# Group J: Cross-regime comparison sanity checks (4 tests)
# ---------------------------------------------------------------------------


def test_cross_regime_low_income_new_wins(computer):
    """At 15L with no deductions, new regime wins decisively.

    Old: taxable 14.5L → slab 2,47,500 + cess 9,900 = 2,57,400.
    New: taxable 14.25L → slab 93,750 + cess 3,750 = 97,500.
    """
    r_old = computer.compute(gross_salary=1_500_000, regime="old")
    r_new = computer.compute(gross_salary=1_500_000, regime="new")
    assert r_new.total_tax_payable < r_old.total_tax_payable
    assert r_old.total_tax_payable == 257_400
    assert r_new.total_tax_payable == 97_500


def test_cross_regime_heavy_deductions_old_wins(computer):
    """At 20L with 7.5L deductions, old regime wins.

    Old: taxable 12L → slab 1,72,500 + cess 6,900 = 1,79,400.
    New: taxable 19.25L → slab 1,85,000 + cess 7,400 = 1,92,400.
    """
    deductions = {
        "80C": 150_000,
        "80CCD1B": 50_000,
        "80D": 25_000,
        "80E": 200_000,
        "24b": 200_000,
        "80G": 125_000,
    }
    r_old = computer.compute(gross_salary=2_000_000, regime="old", deductions=deductions)
    r_new = computer.compute(gross_salary=2_000_000, regime="new", deductions=deductions)
    assert r_old.total_tax_payable < r_new.total_tax_payable
    assert r_old.total_tax_payable == 179_400
    assert r_new.total_tax_payable == 192_400


def test_cross_regime_zero_income_both_zero(computer):
    """Zero income → zero tax under both regimes."""
    r_old = computer.compute(gross_salary=0, regime="old")
    r_new = computer.compute(gross_salary=0, regime="new")
    assert r_old.total_tax_payable == 0
    assert r_new.total_tax_payable == 0


def test_cross_regime_high_income_no_deductions_new_wins(computer):
    """At 50L with no deductions, new regime wins by ~₹2.5L.

    Old: taxable 49.5L → slab 12,97,500 + cess 51,900 = 13,49,400.
    New: taxable 49.25L → slab 10,57,500 + cess 42,300 = 10,99,800.
    """
    r_old = computer.compute(gross_salary=5_000_000, regime="old")
    r_new = computer.compute(gross_salary=5_000_000, regime="new")
    assert r_new.total_tax_payable < r_old.total_tax_payable
    savings = r_old.total_tax_payable - r_new.total_tax_payable
    assert savings == 249_600


# ---------------------------------------------------------------------------
# Group K: Age-threshold boundary edge cases (2 tests)
# ---------------------------------------------------------------------------


def test_age_comparison_at_550K_taxable(computer):
    """All three age categories at 5.5L taxable (above rebate, no surcharge).

    Below-60: slab 22,500 + cess 900 = 23,400.
    Senior:   slab 20,000 + cess 800 = 20,800.
    Super-senior: slab 10,000 + cess 400 = 10,400.

    Super-senior saves 50K@5%=2,500 + 200K@(5→0%)=10,000 vs below-60.
    """
    r_below = computer.compute(gross_salary=600_000, regime="old", age_category="below_60")
    r_senior = computer.compute(gross_salary=600_000, regime="old", age_category="senior")
    r_super = computer.compute(gross_salary=600_000, regime="old", age_category="super_senior")

    assert r_below.total_tax_payable == 23_400
    assert r_senior.total_tax_payable == 20_800
    assert r_super.total_tax_payable == 10_400

    # Strict ordering: below_60 pays most, super_senior pays least
    assert r_below.total_tax_payable > r_senior.total_tax_payable > r_super.total_tax_payable


def test_super_senior_natural_zero_vs_below60_rebated_zero(computer):
    """At 5L taxable both pay zero, but via different mechanisms.

    Super-senior: 5L entirely in 0% slab → tax = 0, no rebate needed.
    Below-60: slab 12,500 fully covered by the 87A rebate (cap 12,500);
    cess applies on the post-rebate tax of zero → total 0.
    """
    r_super = computer.compute(gross_salary=550_000, regime="old", age_category="super_senior")
    r_below = computer.compute(gross_salary=550_000, regime="old", age_category="below_60")

    assert r_super.tax_on_normal_income == 0
    assert r_super.rebate_87a == 0  # nothing to rebate
    assert r_super.total_tax_payable == 0

    assert r_below.tax_on_normal_income == 12_500
    assert r_below.rebate_87a == 12_500
    assert r_below.total_tax_payable == 0
