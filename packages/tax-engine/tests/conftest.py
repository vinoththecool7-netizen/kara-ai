"""Shared fixtures for the Kara tax engine test suite."""

from __future__ import annotations

import pytest

from kara_tax_engine import (
    CapitalGainsCalculator,
    DeductionOptimizer,
    RegimeComparator,
    TaxComputer,
)
from kara_tax_engine.loader import RuleSet
from kara_tax_engine.models import (
    AgeCategory,
    Deductions,
    HRADetails,
    Regime,
    SalaryIncome,
    TaxProfile,
)

# ---------------------------------------------------------------------------
# Engine fixtures (session-scoped — immutable, safe to share)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def computer() -> TaxComputer:
    return TaxComputer(fy="2025-26")


@pytest.fixture(scope="session")
def comparator() -> RegimeComparator:
    return RegimeComparator(fy="2025-26")


@pytest.fixture(scope="session")
def rules() -> RuleSet:
    return RuleSet("2025-26")


@pytest.fixture(scope="session")
def cg_calc() -> CapitalGainsCalculator:
    return CapitalGainsCalculator(fy="2025-26")


@pytest.fixture(scope="session")
def optimizer() -> DeductionOptimizer:
    return DeductionOptimizer(fy="2025-26")


# ---------------------------------------------------------------------------
# Profile fixtures (function-scoped — tests must not mutate shared profiles)
# ---------------------------------------------------------------------------


@pytest.fixture()
def profile_basic_new() -> TaxProfile:
    """Standard salaried taxpayer, new regime, no deductions."""
    return TaxProfile(gross_salary=1_500_000, regime=Regime.NEW)


@pytest.fixture()
def profile_basic_old() -> TaxProfile:
    """Standard salaried taxpayer, old regime, typical deductions."""
    return TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(section_80c=150_000, section_80d=25_000),
    )


@pytest.fixture()
def profile_senior_old() -> TaxProfile:
    """Senior citizen (60–80), old regime."""
    return TaxProfile(
        gross_salary=800_000,
        regime=Regime.OLD,
        age_category=AgeCategory.SENIOR,
        deductions=Deductions(section_80c=100_000, section_80ttb=50_000),
    )


@pytest.fixture()
def profile_super_senior() -> TaxProfile:
    """Super senior (80+), old regime, no deductions."""
    return TaxProfile(
        gross_salary=600_000,
        regime=Regime.OLD,
        age_category=AgeCategory.SUPER_SENIOR,
    )


@pytest.fixture()
def profile_rebate_boundary() -> TaxProfile:
    """Gross=12.75L → taxable=12L exactly. Tests the 87A rebate boundary."""
    return TaxProfile(gross_salary=1_275_000, regime=Regime.NEW)


@pytest.fixture()
def profile_high_income() -> TaxProfile:
    """6 Cr gross — surcharge zone, new regime."""
    return TaxProfile(gross_salary=60_000_000, regime=Regime.NEW)


@pytest.fixture()
def profile_hra() -> TaxProfile:
    """Old regime salaried taxpayer with HRA details."""
    return TaxProfile(
        regime=Regime.OLD,
        salary=SalaryIncome(basic=600_000, hra_received=240_000, special_allowance=200_000),
        hra_details=HRADetails(
            hra_received=240_000,
            basic_salary=600_000,
            rent_paid=180_000,
            is_metro=True,
        ),
    )
