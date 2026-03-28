"""Tests for the enhanced RegimeComparator.

Groups:
  A. Basic Comparison (4 tests)
  B. Breakeven Deductions (4 tests)
  C. Explanation & Metadata (4 tests)
  D. Edge Cases (3 tests)
"""

from __future__ import annotations

from kara_tax_engine.models import (
    AgeCategory,
    Deductions,
    Regime,
    TaxProfile,
)

# ---------------------------------------------------------------------------
# Group A: Basic Comparison (4 tests)
# ---------------------------------------------------------------------------


def test_compare_new_regime_wins_no_deductions(comparator):
    """15L salary, no deductions -- new regime should win."""
    profile = TaxProfile(gross_salary=1_500_000)
    result = comparator.compare(profile)
    assert result.recommended_regime == Regime.NEW
    assert result.savings > 0


def test_compare_old_regime_wins_heavy_deductions(comparator):
    """15L salary with heavy deductions (incl. 80E) -- old regime should win.

    Old regime: 14.5L - 675K deductions = 7.75L taxable
      Tax: 0 + 12,500 + 55,000 = 67,500, cess 2,700 -> ~70,200
    New regime: 14.25L taxable
      Tax: 0 + 20,000 + 40,000 + 33,750 = 93,750, cess 3,750 -> 97,500
    Old wins by ~27,300.
    """
    profile = TaxProfile(
        gross_salary=1_500_000,
        deductions=Deductions(
            section_80c=150_000,
            section_80d=25_000,
            section_80ccd_1b=50_000,
            section_80e=200_000,
            section_24b=200_000,
        ),
    )
    result = comparator.compare(profile)
    assert result.recommended_regime == Regime.OLD
    assert result.savings > 0


def test_compare_returns_both_breakdowns(comparator):
    """Verify both breakdowns are present and correctly labelled."""
    profile = TaxProfile(gross_salary=1_200_000)
    result = comparator.compare(profile)
    assert result.old_regime.regime == Regime.OLD
    assert result.new_regime.regime == Regime.NEW
    assert result.old_regime.total_tax_payable >= 0
    assert result.new_regime.total_tax_payable >= 0


def test_compare_savings_is_absolute_difference(comparator):
    """Savings must equal abs(old_tax - new_tax)."""
    profile = TaxProfile(gross_salary=1_800_000)
    result = comparator.compare(profile)
    expected = abs(result.old_regime.total_tax_payable - result.new_regime.total_tax_payable)
    assert result.savings == expected


# ---------------------------------------------------------------------------
# Group B: Breakeven Deductions (4 tests)
# ---------------------------------------------------------------------------


def test_breakeven_at_moderate_income(comparator):
    """20L salary with large non-80C deductions. Breakeven should be in range.

    Without 80C, old is slightly above new. Adding 80C should close the gap.
    Old (no 80C): 19.5L - 625K = 13.25L taxable -> ~218,400
    New: 19.25L taxable -> ~192,400
    Gap ~26,000. At 30% marginal, breakeven ~84K of 80C.
    """
    profile = TaxProfile(
        gross_salary=2_000_000,
        deductions=Deductions(
            section_80d=25_000,
            section_80ccd_1b=50_000,
            section_80e=350_000,
            section_24b=200_000,
        ),
    )
    result = comparator.compare(profile)
    assert result.recommended_regime == Regime.NEW
    assert 0 < result.breakeven_deductions <= 150_000
    # Verify: at breakeven amount, old regime tax <= new regime tax
    verify_ded = profile.deductions.model_copy(
        update={"section_80c": result.breakeven_deductions},
    )
    verify_profile = TaxProfile(
        gross_salary=2_000_000,
        regime=Regime.OLD,
        deductions=verify_ded,
    )
    old_at_be = comparator.computer.compute_from_profile(verify_profile)
    assert old_at_be.total_tax_payable <= result.new_regime.total_tax_payable


def test_breakeven_zero_when_old_already_wins(comparator):
    """Heavy deductions -> old already wins -> breakeven = 0."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        deductions=Deductions(
            section_80c=150_000,
            section_80d=25_000,
            section_80ccd_1b=50_000,
            section_80e=200_000,
            section_24b=200_000,
        ),
    )
    result = comparator.compare(profile)
    assert result.recommended_regime == Regime.OLD
    assert result.breakeven_deductions == 0


def test_breakeven_zero_when_unreachable(comparator):
    """Very low income (5L) -- even max 80C can't help old."""
    profile = TaxProfile(gross_salary=500_000)
    result = comparator.compare(profile)
    assert result.breakeven_deductions == 0


def test_breakeven_at_high_income(comparator):
    """50L salary -- result should be 0 or a plausible value."""
    profile = TaxProfile(gross_salary=5_000_000)
    result = comparator.compare(profile)
    assert result.breakeven_deductions >= 0
    assert result.breakeven_deductions <= 150_000


# ---------------------------------------------------------------------------
# Group C: Explanation & Metadata (4 tests)
# ---------------------------------------------------------------------------


def test_explanation_mentions_recommended_regime(comparator):
    """Explanation should mention the recommended regime name."""
    profile = TaxProfile(gross_salary=1_500_000)
    result = comparator.compare(profile)
    regime_name = "Old" if result.recommended_regime == Regime.OLD else "New"
    assert regime_name in result.explanation


def test_explanation_mentions_savings(comparator):
    """Savings amount should appear in the explanation."""
    profile = TaxProfile(gross_salary=1_800_000)
    result = comparator.compare(profile)
    # The savings value is formatted with commas; check the number
    assert str(result.savings) in result.explanation.replace(",", "")


def test_compare_effective_tax_rates_populated(comparator):
    """Both breakdowns should have non-negative effective_tax_rate."""
    profile = TaxProfile(gross_salary=1_500_000)
    result = comparator.compare(profile)
    assert result.old_regime.effective_tax_rate >= 0
    assert result.new_regime.effective_tax_rate >= 0


def test_compare_preserves_age_category(comparator):
    """Senior citizen profile -- both breakdowns keep age_category."""
    profile = TaxProfile(
        gross_salary=1_000_000,
        age_category=AgeCategory.SENIOR,
        deductions=Deductions(section_80c=100_000, section_80ttb=50_000),
    )
    result = comparator.compare(profile)
    assert result.old_regime.age_category == AgeCategory.SENIOR
    assert result.new_regime.age_category == AgeCategory.SENIOR


# ---------------------------------------------------------------------------
# Group D: Edge Cases (3 tests)
# ---------------------------------------------------------------------------


def test_compare_zero_income(comparator):
    """Zero salary -> both taxes 0, savings 0."""
    profile = TaxProfile(gross_salary=0)
    result = comparator.compare(profile)
    assert result.old_regime.total_tax_payable == 0
    assert result.new_regime.total_tax_payable == 0
    assert result.savings == 0


def test_compare_very_high_income_surcharge(comparator):
    """6 Cr salary -> surcharge zone, verify surcharge difference."""
    profile = TaxProfile(gross_salary=60_000_000)
    result = comparator.compare(profile)
    # Both should have meaningful tax amounts
    assert result.old_regime.total_tax_payable > 0
    assert result.new_regime.total_tax_payable > 0
    # Surcharge should apply to at least one regime
    has_surcharge = result.old_regime.surcharge_amount > 0 or result.new_regime.surcharge_amount > 0
    assert has_surcharge
    assert result.savings > 0


def test_compare_equal_tax_both_regimes(comparator):
    """Construct a case where taxes are equal or very close.

    Search at higher incomes (above 87A rebate zone) where old regime
    with appropriate deductions can approach new regime tax.
    """
    best_savings = None
    for salary in range(1_500_000, 2_500_001, 100_000):
        for ded_80e in range(0, 500_001, 25_000):
            p = TaxProfile(
                gross_salary=salary,
                deductions=Deductions(
                    section_80c=150_000,
                    section_80d=25_000,
                    section_80e=ded_80e,
                ),
            )
            r = comparator.compare(p)
            if best_savings is None or r.savings < best_savings:
                best_savings = r.savings
            if r.savings == 0:
                break
        if best_savings == 0:
            break

    assert best_savings is not None
    # Allow near-equality: savings within ₹5000
    assert best_savings <= 5000, f"Could not find near-equal case; best savings={best_savings}"
