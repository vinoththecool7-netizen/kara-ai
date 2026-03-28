"""Tests for remaining deductions (80E-80U, 24b) and integration profiles (FY 2025-26).

Sections covered:
  80E  — Education loan interest (no cap, old only)
  80G  — Donations (no cap enforced, old only)
  80TTA — Savings interest below-60 (₹10K cap, old only)
  80TTB — Senior savings interest (₹50K cap, old only)
  80U  — Self disability (₹75K / ₹1.25L, old only)
  80DD — Dependent disability (₹75K / ₹1.25L, old only)
  24(b) — Home loan interest (₹2L cap self-occupied, old only)

Integration tests verify multiple deductions, slab tax, cess, and final payable
for realistic taxpayer profiles under both regimes.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Group A: 80E Education Loan Interest (4 tests)
# ---------------------------------------------------------------------------


def test_80e_no_cap(computer):
    """80E has no monetary cap — 3L claimed, 3L allowed."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80E": 300_000})
    dr = [d for d in r.deductions_applied if d.section == "80E"]
    assert len(dr) == 1
    assert dr[0].claimed == 300_000
    assert dr[0].allowed == 300_000
    assert r.total_deductions == 300_000


def test_80e_large_amount(computer):
    """80E allows even very large amounts — 10L interest fully deductible."""
    r = computer.compute(gross_salary=2_000_000, regime="old", deductions={"80E": 1_000_000})
    dr = [d for d in r.deductions_applied if d.section == "80E"]
    assert len(dr) == 1
    assert dr[0].allowed == 1_000_000


def test_80e_small_amount(computer):
    """80E small claim — 5K fully allowed."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80E": 5_000})
    dr = [d for d in r.deductions_applied if d.section == "80E"]
    assert len(dr) == 1
    assert dr[0].allowed == 5_000


def test_80e_rejected_in_new_regime(computer):
    """80E is old-regime only — new regime ignores it entirely."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80E": 200_000})
    assert r.total_deductions == 0
    sections = [d.section for d in r.deductions_applied]
    assert "80E" not in sections


# ---------------------------------------------------------------------------
# Group B: 80G Donations (4 tests)
# ---------------------------------------------------------------------------


def test_80g_basic_donation(computer):
    """80G basic donation — 50K claimed, 50K allowed (no cap enforced)."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80G": 50_000})
    dr = [d for d in r.deductions_applied if d.section == "80G"]
    assert len(dr) == 1
    assert dr[0].allowed == 50_000


def test_80g_large_donation(computer):
    """80G large donation — 5L claimed, 5L allowed."""
    r = computer.compute(gross_salary=2_000_000, regime="old", deductions={"80G": 500_000})
    dr = [d for d in r.deductions_applied if d.section == "80G"]
    assert len(dr) == 1
    assert dr[0].allowed == 500_000


def test_80g_rejected_in_new_regime(computer):
    """80G is old-regime only — new regime ignores it."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"80G": 50_000})
    assert r.total_deductions == 0
    sections = [d.section for d in r.deductions_applied]
    assert "80G" not in sections


def test_80g_zero_donation(computer):
    """80G with zero amount — no entry created in deductions_applied."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80G": 0})
    sections = [d.section for d in r.deductions_applied]
    assert "80G" not in sections


# ---------------------------------------------------------------------------
# Group C: 80TTA/80TTB Savings Interest (6 tests)
# ---------------------------------------------------------------------------


def test_80tta_within_cap_below60(computer):
    """80TTA below 60: 8K claimed, within 10K cap — fully allowed."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="below_60",
        deductions={"80TTA": 8_000},
    )
    dr = [d for d in r.deductions_applied if d.section == "80TTA"]
    assert len(dr) == 1
    assert dr[0].allowed == 8_000


def test_80tta_exceeds_cap_below60(computer):
    """80TTA below 60: 15K claimed, capped at 10K."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="below_60",
        deductions={"80TTA": 15_000},
    )
    dr = [d for d in r.deductions_applied if d.section == "80TTA"]
    assert len(dr) == 1
    assert dr[0].claimed == 15_000
    assert dr[0].allowed == 10_000
    assert dr[0].cap == 10_000


def test_80tta_exact_cap(computer):
    """80TTA at exact 10K cap — fully allowed."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="below_60",
        deductions={"80TTA": 10_000},
    )
    dr = [d for d in r.deductions_applied if d.section == "80TTA"]
    assert len(dr) == 1
    assert dr[0].allowed == 10_000


def test_80ttb_senior_50k_cap(computer):
    """80TTB for senior citizen: 50K claimed, at cap — fully allowed."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80TTB": 50_000},
    )
    dr = [d for d in r.deductions_applied if d.section == "80TTB"]
    assert len(dr) == 1
    assert dr[0].allowed == 50_000


def test_80ttb_senior_exceeds_cap(computer):
    """80TTB for senior: 60K claimed, capped at 50K."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80TTB": 60_000},
    )
    dr = [d for d in r.deductions_applied if d.section == "80TTB"]
    assert len(dr) == 1
    assert dr[0].allowed == 50_000
    assert dr[0].cap == 50_000


def test_80tta_ignored_for_senior(computer):
    """80TTA declared by senior (no 80TTB) — silently ignored.

    Code checks age first: for seniors it ONLY processes 80TTB branch.
    80TTA is never looked at for senior/super_senior.
    """
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80TTA": 10_000},
    )
    sections = [d.section for d in r.deductions_applied]
    assert "80TTA" not in sections
    assert "80TTB" not in sections
    # Confirm no savings-interest deduction at all
    tta_ttb_deductions = [d for d in r.deductions_applied if d.section in ("80TTA", "80TTB")]
    assert len(tta_ttb_deductions) == 0


# ---------------------------------------------------------------------------
# Group D: 80U/80DD Disability (6 tests)
# ---------------------------------------------------------------------------


def test_80u_normal_disability_75k(computer):
    """80U at 75K (< 125K threshold) → normal disability, cap 75K, allowed 75K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80U": 75_000})
    dr = [d for d in r.deductions_applied if d.section == "80U"]
    assert len(dr) == 1
    assert dr[0].cap == 75_000
    assert dr[0].allowed == 75_000


def test_80u_severe_disability_125k(computer):
    """80U at 125K (>= 125K threshold) → severe disability, cap 125K, allowed 125K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80U": 125_000})
    dr = [d for d in r.deductions_applied if d.section == "80U"]
    assert len(dr) == 1
    assert dr[0].cap == 125_000
    assert dr[0].allowed == 125_000


def test_80u_between_75k_and_125k(computer):
    """80U at 100K (< 125K so normal) → cap 75K, allowed min(100K, 75K) = 75K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80U": 100_000})
    dr = [d for d in r.deductions_applied if d.section == "80U"]
    assert len(dr) == 1
    assert dr[0].cap == 75_000
    assert dr[0].allowed == 75_000


def test_80u_above_125k(computer):
    """80U at 200K (>= 125K so severe) → cap 125K, allowed 125K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80U": 200_000})
    dr = [d for d in r.deductions_applied if d.section == "80U"]
    assert len(dr) == 1
    assert dr[0].cap == 125_000
    assert dr[0].allowed == 125_000


def test_80dd_normal_75k(computer):
    """80DD at 75K — normal disability, allowed 75K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80DD": 75_000})
    dr = [d for d in r.deductions_applied if d.section == "80DD"]
    assert len(dr) == 1
    assert dr[0].cap == 75_000
    assert dr[0].allowed == 75_000


def test_80dd_severe_125k(computer):
    """80DD at 150K (>= 125K so severe) → cap 125K, allowed 125K."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80DD": 150_000})
    dr = [d for d in r.deductions_applied if d.section == "80DD"]
    assert len(dr) == 1
    assert dr[0].cap == 125_000
    assert dr[0].allowed == 125_000


# ---------------------------------------------------------------------------
# Group E: Section 24(b) Home Loan Interest (3 tests)
# ---------------------------------------------------------------------------


def test_24b_within_cap(computer):
    """24(b) at 1.5L — within 2L cap, fully allowed."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"24b": 150_000})
    dr = [d for d in r.deductions_applied if d.section == "24(b)"]
    assert len(dr) == 1
    assert dr[0].allowed == 150_000


def test_24b_exceeds_cap(computer):
    """24(b) at 3L — capped at 2L (self-occupied)."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"24b": 300_000})
    dr = [d for d in r.deductions_applied if d.section == "24(b)"]
    assert len(dr) == 1
    assert dr[0].allowed == 200_000
    assert dr[0].cap == 200_000


def test_24b_rejected_in_new_regime(computer):
    """24(b) is old-regime only — new regime ignores it."""
    r = computer.compute(gross_salary=1_000_000, regime="new", deductions={"24b": 200_000})
    sections = [d.section for d in r.deductions_applied]
    assert "24(b)" not in sections
    assert r.total_deductions == 0


# ---------------------------------------------------------------------------
# Group F: Full Integration Profiles (4 tests)
# ---------------------------------------------------------------------------


def test_integration_salaried_heavy_deductions(computer):
    """Old regime, 20L, below_60, with heavy deductions across 6 sections.

    Deductions:
      80C: 150K → allowed 150K (cap)
      80D: 25K → allowed 25K (below cap)
      80D_parents: 25K → allowed 25K (below cap)
      80CCD1B: 50K → allowed 50K (cap)
      80TTA: 10K → allowed 10K (cap)
      24b: 200K → allowed 200K (cap)

    80D: combined claimed = 50K, allowed = 50K, cap = 75K (25K self + 50K parents)
    Total deductions = 150K + 50K + 50K + 10K + 200K = 460K
    Taxable = (20L - 50K) - 460K = 1,950,000 - 460,000 = 1,490,000

    Slabs (below_60): 2.5L@0% + 2.5L@5%(12500) + 5L@20%(100000) + 4.9L@30%(147000) = 259,500
    Cess = ceil(259500 * 0.04) = 10,380
    Total = 269,880
    """
    r = computer.compute(
        gross_salary=2_000_000,
        regime="old",
        age_category="below_60",
        deductions={
            "80C": 150_000,
            "80D": 25_000,
            "80D_parents": 25_000,
            "80CCD1B": 50_000,
            "80TTA": 10_000,
            "24b": 200_000,
        },
    )
    assert r.total_deductions == 460_000
    assert r.taxable_income == 1_490_000
    assert r.tax_on_normal_income == 259_500
    assert r.cess_amount == math.ceil(259_500 * 0.04)
    assert r.total_tax_payable == 269_880
    # Verify multiple deduction sections present
    sections = {d.section for d in r.deductions_applied}
    assert len(r.deductions_applied) >= 5  # 80C, 80CCD(1B), 80D, 80TTA, 24(b)


def test_integration_senior_citizen_profile(computer):
    """Old regime, senior, 12L, with senior-specific deductions.

    Deductions:
      80C: 100K → allowed 100K
      80D: 50K → allowed 50K (senior cap)
      80TTB: 50K → allowed 50K (senior savings)
      80U: 75K → cap 75K (normal), allowed 75K

    Total deductions = 100K + 50K + 50K + 75K = 275K
    Taxable = (12L - 50K) - 275K = 1,150,000 - 275,000 = 875,000

    Senior slabs: 3L@0% + 2L@5%(10000) + 3.75L@20%(75000) = 85,000
    Cess = ceil(85000 * 0.04) = 3,400
    Total = 88,400
    """
    r = computer.compute(
        gross_salary=1_200_000,
        regime="old",
        age_category="senior",
        deductions={
            "80C": 100_000,
            "80D": 50_000,
            "80TTB": 50_000,
            "80U": 75_000,
        },
    )
    assert r.total_deductions == 275_000
    assert r.taxable_income == 875_000
    assert r.tax_on_normal_income == 85_000
    assert r.cess_amount == 3_400
    assert r.total_tax_payable == 88_400


def test_integration_new_regime_only_80ccd2(computer):
    """New regime, 15L — only 80CCD(2) is allowed; other deductions ignored.

    Deductions declared: 80CCD2=100K, 80C=150K, 80D=25K
    Only 80CCD(2) survives new regime filter.
    Total deductions = 100K

    Taxable = (15L - 75K) - 100K = 1,425,000 - 100,000 = 1,325,000

    New regime slabs: 4L@0% + 4L@5%(20000) + 4L@10%(40000) + 1.25L@15%(18750) = 78,750
    Cess = ceil(78750 * 0.04) = 3,150
    Total = 81,900
    """
    r = computer.compute(
        gross_salary=1_500_000,
        regime="new",
        deductions={
            "80CCD2": 100_000,
            "80C": 150_000,
            "80D": 25_000,
        },
    )
    assert r.total_deductions == 100_000
    assert r.taxable_income == 1_325_000
    # Only 80CCD(2) entry
    sections = [d.section for d in r.deductions_applied]
    assert "80CCD(2)" in sections
    assert "80C/80CCC/80CCD(1)" not in sections
    assert "80D" not in sections
    assert r.tax_on_normal_income == 78_750
    assert r.cess_amount == 3_150
    assert r.total_tax_payable == 81_900


def test_integration_kitchen_sink_old_regime(computer):
    """Old regime, below_60, 25L, every deduction type active.

    Deductions:
      80C: 150K → allowed 150K (cap)
      80CCD1B: 50K → allowed 50K (cap)
      80CCD2: 100K → allowed 100K (both regimes)
      80D: 25K → allowed 25K
      80D_parents: 50K → allowed 50K
      80E: 200K → allowed 200K (no cap)
      80G: 100K → allowed 100K (no cap)
      80TTA: 10K → allowed 10K (cap)
      80U: 75K → cap 75K, allowed 75K
      24b: 200K → allowed 200K (cap)

    80D combined: claimed 75K, allowed 75K (cap = 25K+50K = 75K)
    Total = 150K + 50K + 100K + 75K + 200K + 100K + 10K + 75K + 200K = 960K
    Taxable = (25L - 50K) - 960K = 2,450,000 - 960,000 = 1,490,000

    Slabs (below_60): 2.5L@0% + 2.5L@5%(12500) + 5L@20%(100000) + 4.9L@30%(147000) = 259,500
    Cess = ceil(259500 * 0.04) = 10,380
    Total = 269,880
    """
    r = computer.compute(
        gross_salary=2_500_000,
        regime="old",
        age_category="below_60",
        deductions={
            "80C": 150_000,
            "80CCD1B": 50_000,
            "80CCD2": 100_000,
            "80D": 25_000,
            "80D_parents": 50_000,
            "80E": 200_000,
            "80G": 100_000,
            "80TTA": 10_000,
            "80U": 75_000,
            "24b": 200_000,
        },
    )
    assert r.total_deductions == 960_000
    assert r.taxable_income == 1_490_000
    # Verify many deduction entries
    sections = {d.section for d in r.deductions_applied}
    assert len(r.deductions_applied) >= 7
    # Verify key sections are present
    assert "80C/80CCC/80CCD(1)" in sections
    assert "80CCD(1B)" in sections
    assert "80CCD(2)" in sections
    assert "80D" in sections
    assert "80E" in sections
    assert "80G" in sections
    assert "80TTA" in sections
    assert "80U" in sections
    assert "24(b)" in sections
    assert r.tax_on_normal_income == 259_500
    assert r.cess_amount == 10_380
    assert r.total_tax_payable == 269_880
