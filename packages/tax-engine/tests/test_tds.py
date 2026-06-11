"""Tests for the TDS rate lookup engine (FY 2025-26).

Rates and thresholds reflect the Finance (No. 2) Act 2024 (rate cuts
effective 1 Oct 2024) and Finance Act 2025 (threshold increases
effective 1 Apr 2025).
"""
from __future__ import annotations

import pytest

from kara_tax_engine.tds import TDSCalculator


@pytest.fixture(scope="module")
def tds():
    return TDSCalculator(fy="2025-26")


# ---------------------------------------------------------------------------
# Group A: basic lookups
# ---------------------------------------------------------------------------


def test_salary_is_slab_rate(tds):
    r = tds.lookup("salary")
    assert r.section == "192"
    assert r.rate is None  # slab-rate: no flat percentage
    assert r.rate_description == "as per slab"


def test_professional_fees_rate_and_threshold(tds):
    """194J professional services: 10%, threshold raised to 50K by FA 2025."""
    r = tds.lookup("professional_fees")
    assert r.section == "194J"
    assert r.rate == 0.10
    assert r.threshold == 50_000


def test_commission_rate_cut_oct_2024(tds):
    """194H commission/brokerage: cut from 5% to 2% effective 1 Oct 2024."""
    r = tds.lookup("commission")
    assert r.section == "194H"
    assert r.rate == 0.02
    assert r.threshold == 20_000


def test_dividend_threshold_fa2025(tds):
    """194 dividend: 10%, threshold raised from 5K to 10K by FA 2025."""
    r = tds.lookup("dividend")
    assert r.section == "194"
    assert r.rate == 0.10
    assert r.threshold == 10_000


def test_rent_is_monthly_threshold(tds):
    """194-I rent: 50K per MONTH from FY 2025-26 (was 2.4L per year)."""
    r = tds.lookup("rent_land_building")
    assert r.section == "194-I"
    assert r.rate == 0.10
    assert r.threshold == 50_000
    assert r.threshold_period == "monthly"


def test_rent_plant_machinery_2_percent(tds):
    r = tds.lookup("rent_plant_machinery")
    assert r.section == "194-I"
    assert r.rate == 0.02


def test_crypto_vda_1_percent(tds):
    r = tds.lookup("vda_transfer")
    assert r.section == "194S"
    assert r.rate == 0.01


def test_contractor_individual_vs_company(tds):
    assert tds.lookup("contractor_individual").rate == 0.01
    assert tds.lookup("contractor_other").rate == 0.02


# ---------------------------------------------------------------------------
# Group B: amount-based computation
# ---------------------------------------------------------------------------


def test_amount_below_threshold_no_tds(tds):
    r = tds.lookup("professional_fees", amount=40_000)
    assert r.applicable is False
    assert r.tds_amount == 0


def test_amount_above_threshold_computes_tds(tds):
    r = tds.lookup("professional_fees", amount=100_000)
    assert r.applicable is True
    assert r.tds_amount == 10_000  # 10% of full amount once threshold crossed


def test_amount_exactly_at_threshold_not_applicable(tds):
    """TDS triggers when the amount EXCEEDS the threshold."""
    r = tds.lookup("professional_fees", amount=50_000)
    assert r.applicable is False


# ---------------------------------------------------------------------------
# Group C: senior citizens and PAN
# ---------------------------------------------------------------------------


def test_bank_interest_senior_threshold(tds):
    """194A bank interest: FA 2025 thresholds — 50K general, 1L for seniors."""
    general = tds.lookup("interest_bank", amount=80_000)
    senior = tds.lookup("interest_bank", amount=80_000, is_senior=True)
    assert general.applicable is True
    assert general.tds_amount == 8_000
    assert senior.applicable is False
    assert senior.threshold == 100_000


def test_no_pan_forces_20_percent(tds):
    """Section 206AA: missing PAN → higher of the rate or 20%."""
    r = tds.lookup("professional_fees", amount=100_000, has_pan=False)
    assert r.rate == 0.20
    assert r.tds_amount == 20_000
    assert "PAN" in r.note


def test_no_pan_does_not_lower_a_higher_rate(tds):
    """Lottery is 30% — no-PAN must not reduce it to 20%."""
    r = tds.lookup("lottery", amount=50_000, has_pan=False)
    assert r.rate == 0.30


# ---------------------------------------------------------------------------
# Group D: errors and catalogue
# ---------------------------------------------------------------------------


def test_unknown_payment_type_raises_with_known_types(tds):
    with pytest.raises(ValueError) as exc_info:
        tds.lookup("bribes")
    assert "professional_fees" in str(exc_info.value)


def test_all_payment_types_have_section_and_description(tds):
    for payment_type in tds.payment_types():
        r = tds.lookup(payment_type)
        assert r.section, payment_type
        assert r.description, payment_type
