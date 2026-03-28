"""Tests for Pydantic data models."""

from __future__ import annotations

import pytest

from kara_tax_engine.models import (
    AgeCategory,
    DeductionResult,
    Deductions,
    Regime,
    SalaryIncome,
    SlabBreakdown,
    TaxBreakdown,
    TaxProfile,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


def test_regime_values():
    assert Regime.OLD.value == "old"
    assert Regime.NEW.value == "new"
    assert Regime("old") == Regime.OLD
    assert Regime("new") == Regime.NEW


def test_age_category_values():
    assert AgeCategory.BELOW_60.value == "below_60"
    assert AgeCategory.SENIOR.value == "senior"
    assert AgeCategory.SUPER_SENIOR.value == "super_senior"
    assert AgeCategory("senior") == AgeCategory.SENIOR


def test_invalid_regime_raises():
    with pytest.raises(ValueError):
        Regime("invalid")


def test_invalid_age_category_raises():
    with pytest.raises(ValueError):
        AgeCategory("child")


# ---------------------------------------------------------------------------
# SalaryIncome
# ---------------------------------------------------------------------------


def test_salary_total_from_components():
    s = SalaryIncome(basic=500_000, da=100_000, hra_received=200_000, special_allowance=100_000)
    assert s.total() == 900_000


def test_salary_total_from_gross():
    s = SalaryIncome(basic=200_000, da=50_000, gross_salary=1_500_000)
    assert s.total() == 1_500_000  # gross_salary takes precedence


def test_salary_defaults_zero():
    assert SalaryIncome().total() == 0


# ---------------------------------------------------------------------------
# Deductions
# ---------------------------------------------------------------------------


def test_deductions_all_zero():
    d = Deductions()
    assert d.section_80c == 0
    assert d.section_80d == 0
    assert d.section_80ccd_1b == 0
    assert d.section_80ttb == 0
    assert d.section_24b == 0


def test_deductions_field_assignment():
    d = Deductions(section_80c=150_000, section_80d=25_000)
    assert d.section_80c == 150_000
    assert d.section_80d == 25_000


# ---------------------------------------------------------------------------
# TaxProfile
# ---------------------------------------------------------------------------


def test_profile_defaults():
    p = TaxProfile()
    assert p.financial_year == "2025-26"
    assert p.assessment_year == "2026-27"
    assert p.regime == Regime.NEW
    assert p.age_category == AgeCategory.BELOW_60
    assert p.gross_salary == 0


def test_profile_get_gross_salary_direct():
    p = TaxProfile(gross_salary=1_000_000)
    assert p.get_gross_salary() == 1_000_000


def test_profile_get_gross_salary_from_salary():
    p = TaxProfile(salary=SalaryIncome(basic=500_000, da=100_000))
    assert p.get_gross_salary() == 600_000


def test_profile_salary_overrides_gross_salary_field():
    """When salary object is set, it takes priority over the gross_salary field."""
    p = TaxProfile(gross_salary=999_999, salary=SalaryIncome(basic=400_000))
    assert p.get_gross_salary() == 400_000


def test_profile_model_copy_regime():
    p = TaxProfile(regime=Regime.NEW)
    p_old = p.model_copy(update={"regime": Regime.OLD})
    assert p.regime == Regime.NEW
    assert p_old.regime == Regime.OLD


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


def test_tax_breakdown_add_step():
    tb = TaxBreakdown(
        regime=Regime.NEW,
        financial_year="2025-26",
        assessment_year="2026-27",
        age_category=AgeCategory.BELOW_60,
    )
    assert tb.computation_steps == []
    tb.add_step("test step")
    assert tb.computation_steps == ["test step"]


def test_slab_breakdown_fields():
    sb = SlabBreakdown(lower=0, upper=400_000, rate=0.0, taxable_in_slab=400_000, tax_in_slab=0)
    assert sb.lower == 0
    assert sb.upper == 400_000
    assert sb.rate == 0.0
    assert sb.taxable_in_slab == 400_000
    assert sb.tax_in_slab == 0


def test_slab_breakdown_open_upper():
    sb = SlabBreakdown(
        lower=2_400_000, upper=None, rate=0.30, taxable_in_slab=100_000, tax_in_slab=30_000
    )
    assert sb.upper is None


def test_deduction_result_fields():
    dr = DeductionResult(section="80C", claimed=200_000, allowed=150_000, cap=150_000)
    assert dr.allowed <= dr.claimed
    assert dr.cap == 150_000
    assert dr.regime_applicable is True
