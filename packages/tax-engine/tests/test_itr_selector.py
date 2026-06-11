"""Tests for the ITR form selector (AY 2026-27 rules)."""
from __future__ import annotations

import pytest

from kara_tax_engine.itr_selector import ITRSelector


@pytest.fixture(scope="module")
def selector():
    return ITRSelector(fy="2025-26")


# ---------------------------------------------------------------------------
# Entity-type shortcuts
# ---------------------------------------------------------------------------


def test_company_itr6(selector):
    r = selector.select(entity_type="company")
    assert r.form == "ITR-6"


def test_firm_itr5(selector):
    assert selector.select(entity_type="firm").form == "ITR-5"
    assert selector.select(entity_type="llp").form == "ITR-5"


def test_trust_itr7(selector):
    assert selector.select(entity_type="trust").form == "ITR-7"


# ---------------------------------------------------------------------------
# ITR-1 (Sahaj)
# ---------------------------------------------------------------------------


def test_simple_salaried_itr1(selector):
    r = selector.select(total_income=1_200_000, has_salary=True, house_property_count=1)
    assert r.form == "ITR-1"


def test_itr1_allows_small_112a_ltcg(selector):
    """From AY 2025-26, ITR-1 permits LTCG u/s 112A up to ₹1.25L."""
    r = selector.select(
        total_income=1_200_000,
        has_salary=True,
        ltcg_112a_amount=100_000,
    )
    assert r.form == "ITR-1"


def test_income_above_50l_excludes_itr1(selector):
    r = selector.select(total_income=6_000_000, has_salary=True)
    assert r.form == "ITR-2"


def test_two_house_properties_excludes_itr1(selector):
    r = selector.select(total_income=1_000_000, has_salary=True, house_property_count=2)
    assert r.form == "ITR-2"


def test_non_resident_excludes_itr1(selector):
    r = selector.select(
        total_income=1_000_000, has_salary=True, residential_status="non_resident"
    )
    assert r.form == "ITR-2"


def test_agri_income_above_5k_excludes_itr1(selector):
    r = selector.select(total_income=1_000_000, has_salary=True, agricultural_income=50_000)
    assert r.form == "ITR-2"


def test_director_or_unlisted_shares_excludes_itr1(selector):
    assert selector.select(total_income=1_000_000, has_salary=True, is_director=True).form == "ITR-2"
    assert (
        selector.select(total_income=1_000_000, has_salary=True, has_unlisted_shares=True).form
        == "ITR-2"
    )


def test_foreign_assets_exclude_itr1(selector):
    r = selector.select(total_income=1_000_000, has_salary=True, has_foreign_assets=True)
    assert r.form == "ITR-2"


# ---------------------------------------------------------------------------
# ITR-2 / ITR-3
# ---------------------------------------------------------------------------


def test_large_ltcg_112a_requires_itr2(selector):
    r = selector.select(total_income=2_000_000, has_salary=True, ltcg_112a_amount=300_000)
    assert r.form == "ITR-2"


def test_other_capital_gains_require_itr2(selector):
    r = selector.select(total_income=2_000_000, has_salary=True, has_other_capital_gains=True)
    assert r.form == "ITR-2"


def test_crypto_requires_itr2(selector):
    r = selector.select(total_income=1_000_000, has_salary=True, has_crypto_income=True)
    assert r.form == "ITR-2"


def test_business_income_itr3(selector):
    r = selector.select(total_income=2_000_000, has_business=True)
    assert r.form == "ITR-3"


# ---------------------------------------------------------------------------
# ITR-4 (Sugam)
# ---------------------------------------------------------------------------


def test_presumptive_business_itr4(selector):
    r = selector.select(total_income=2_000_000, has_business=True, is_presumptive=True)
    assert r.form == "ITR-4"


def test_presumptive_above_50l_falls_back_to_itr3(selector):
    r = selector.select(total_income=6_000_000, has_business=True, is_presumptive=True)
    assert r.form == "ITR-3"


def test_presumptive_director_cannot_use_itr4(selector):
    r = selector.select(
        total_income=2_000_000, has_business=True, is_presumptive=True, is_director=True
    )
    assert r.form == "ITR-3"


def test_presumptive_non_resident_cannot_use_itr4(selector):
    r = selector.select(
        total_income=2_000_000,
        has_business=True,
        is_presumptive=True,
        residential_status="non_resident",
    )
    assert r.form == "ITR-3"


# ---------------------------------------------------------------------------
# Output quality
# ---------------------------------------------------------------------------


def test_reason_is_populated(selector):
    r = selector.select(total_income=1_000_000, has_salary=True)
    assert len(r.reason) > 10


def test_exclusions_listed_when_itr1_denied(selector):
    r = selector.select(total_income=1_000_000, has_salary=True, is_director=True)
    assert any("director" in e.lower() for e in r.exclusions_applied)
