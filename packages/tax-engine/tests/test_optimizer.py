"""Tests for DeductionOptimizer — deduction gap detection & suggestions."""

from __future__ import annotations

from kara_tax_engine.models import (
    AgeCategory,
    Deductions,
    Regime,
    TaxProfile,
)
from kara_tax_engine.optimizer import DeductionOptimizer

# ---------------------------------------------------------------------------
# Group A: 80C Gap Detection (4 tests)
# ---------------------------------------------------------------------------


def test_optimizer_80c_full_gap(optimizer: DeductionOptimizer) -> None:
    """15L old regime, zero 80C -> full 1.5L gap."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    assert result.section_80c_used == 0
    assert result.section_80c_remaining == 150_000
    section_80c_suggestions = [s for s in result.suggestions if s.section == "80C"]
    assert len(section_80c_suggestions) == 3
    for s in section_80c_suggestions:
        assert s.suggested_amount == 150_000


def test_optimizer_80c_partial_gap(optimizer: DeductionOptimizer) -> None:
    """15L old regime, 80C=80K -> remaining 70K."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(section_80c=80_000),
    )
    result = optimizer.optimize(profile)
    assert result.section_80c_used == 80_000
    assert result.section_80c_remaining == 70_000
    section_80c_suggestions = [s for s in result.suggestions if s.section == "80C"]
    assert len(section_80c_suggestions) == 3
    for s in section_80c_suggestions:
        assert s.suggested_amount == 70_000


def test_optimizer_80c_already_maxed(optimizer: DeductionOptimizer) -> None:
    """80C=150K -> remaining 0, no 80C suggestions."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(section_80c=150_000),
    )
    result = optimizer.optimize(profile)
    assert result.section_80c_used == 150_000
    assert result.section_80c_remaining == 0
    section_80c_suggestions = [s for s in result.suggestions if s.section == "80C"]
    assert len(section_80c_suggestions) == 0


def test_optimizer_80c_exceeds_cap(optimizer: DeductionOptimizer) -> None:
    """80C=200K declared -> used capped at 150K, remaining 0."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(section_80c=200_000),
    )
    result = optimizer.optimize(profile)
    assert result.section_80c_used == 150_000
    assert result.section_80c_remaining == 0


# ---------------------------------------------------------------------------
# Group B: 80D Gap Detection (3 tests)
# ---------------------------------------------------------------------------


def test_optimizer_80d_no_insurance(optimizer: DeductionOptimizer) -> None:
    """Zero 80D, below-60 -> suggest up to 75K (25K self + 50K parents)."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        age_category=AgeCategory.BELOW_60,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    assert result.section_80d_used == 0
    assert result.section_80d_remaining == 75_000
    d_suggestions = [s for s in result.suggestions if s.section == "80D"]
    assert len(d_suggestions) == 1
    assert d_suggestions[0].suggested_amount == 75_000
    assert d_suggestions[0].instrument == "Health Insurance"


def test_optimizer_80d_self_only(optimizer: DeductionOptimizer) -> None:
    """80D=25K self, no parents -> should suggest parents insurance."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        age_category=AgeCategory.BELOW_60,
        deductions=Deductions(section_80d=25_000),
    )
    result = optimizer.optimize(profile)
    # Used = 25K self + 0 parents = 25K
    assert result.section_80d_used == 25_000
    # Remaining = 75K - 25K = 50K (parents insurance)
    assert result.section_80d_remaining == 50_000
    d_suggestions = [s for s in result.suggestions if s.section == "80D"]
    assert len(d_suggestions) == 1
    assert d_suggestions[0].suggested_amount == 50_000


def test_optimizer_80d_maxed(optimizer: DeductionOptimizer) -> None:
    """80D=25K + parents=50K below-60 -> no 80D suggestion."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        age_category=AgeCategory.BELOW_60,
        deductions=Deductions(section_80d=25_000, section_80d_parents=50_000),
    )
    result = optimizer.optimize(profile)
    assert result.section_80d_used == 75_000
    assert result.section_80d_remaining == 0
    d_suggestions = [s for s in result.suggestions if s.section == "80D"]
    assert len(d_suggestions) == 0


# ---------------------------------------------------------------------------
# Group C: NPS 80CCD(1B) (3 tests)
# ---------------------------------------------------------------------------


def test_optimizer_nps_unused(optimizer: DeductionOptimizer) -> None:
    """Zero 80CCD1B -> suggest 50K NPS."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    assert result.section_80ccd_1b_used == 0
    assert result.section_80ccd_1b_remaining == 50_000
    nps = [s for s in result.suggestions if s.section == "80CCD(1B)"]
    assert len(nps) == 1
    assert nps[0].suggested_amount == 50_000
    assert nps[0].instrument == "NPS"


def test_optimizer_nps_partial(optimizer: DeductionOptimizer) -> None:
    """80CCD1B=20K -> remaining 30K."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(section_80ccd_1b=20_000),
    )
    result = optimizer.optimize(profile)
    assert result.section_80ccd_1b_used == 20_000
    assert result.section_80ccd_1b_remaining == 30_000
    nps = [s for s in result.suggestions if s.section == "80CCD(1B)"]
    assert len(nps) == 1
    assert nps[0].suggested_amount == 30_000


def test_optimizer_nps_full(optimizer: DeductionOptimizer) -> None:
    """80CCD1B=50K -> remaining 0, no NPS suggestion."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(section_80ccd_1b=50_000),
    )
    result = optimizer.optimize(profile)
    assert result.section_80ccd_1b_used == 50_000
    assert result.section_80ccd_1b_remaining == 0
    nps = [s for s in result.suggestions if s.section == "80CCD(1B)"]
    assert len(nps) == 0


# ---------------------------------------------------------------------------
# Group D: Edge Cases (2 tests)
# ---------------------------------------------------------------------------


def test_optimizer_all_maxed(optimizer: DeductionOptimizer) -> None:
    """All deductions maxed -> no suggestions, zero saving."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        age_category=AgeCategory.BELOW_60,
        deductions=Deductions(
            section_80c=150_000,
            section_80ccd_1b=50_000,
            section_80d=25_000,
            section_80d_parents=50_000,
        ),
    )
    result = optimizer.optimize(profile)
    assert len(result.suggestions) == 0
    assert result.total_potential_saving == 0


def test_optimizer_zero_income(optimizer: DeductionOptimizer) -> None:
    """Zero salary -> current_tax=0, no suggestions."""
    profile = TaxProfile(
        gross_salary=0,
        regime=Regime.OLD,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    assert result.current_tax == 0
    assert len(result.suggestions) == 0


# ---------------------------------------------------------------------------
# Group E: Quality (3 tests)
# ---------------------------------------------------------------------------


def test_optimizer_suggestions_sorted_by_saving(
    optimizer: DeductionOptimizer,
) -> None:
    """Suggestions should be sorted descending by potential_tax_saving."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    savings = [s.potential_tax_saving for s in result.suggestions]
    assert savings == sorted(savings, reverse=True)
    # Should have suggestions from multiple sections
    assert len(result.suggestions) >= 3


def test_optimizer_saving_accuracy(optimizer: DeductionOptimizer) -> None:
    """Top suggestion saving matches manual delta computation."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    assert len(result.suggestions) > 0

    top = result.suggestions[0]
    # Manually compute the saving
    manual_saving = optimizer._compute_suggestion_saving(
        profile.model_copy(update={"regime": Regime.OLD}),
        result.current_tax,
        top.section,
        top.suggested_amount,
    )
    assert top.potential_tax_saving == manual_saving
    assert top.potential_tax_saving > 0


def test_optimizer_total_saving_correct(
    optimizer: DeductionOptimizer,
) -> None:
    """total_potential_saving == current_tax - optimized_tax, non-negative."""
    profile = TaxProfile(
        gross_salary=1_500_000,
        regime=Regime.OLD,
        deductions=Deductions(),
    )
    result = optimizer.optimize(profile)
    assert result.total_potential_saving == (result.current_tax - result.optimized_tax)
    assert result.total_potential_saving >= 0
    assert result.optimized_tax >= 0
