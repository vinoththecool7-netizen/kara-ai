"""Tests for the YAML rule loader."""

from __future__ import annotations

import pytest

from kara_tax_engine.loader import RuleSet

# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_ruleset_loads_2025_26():
    r = RuleSet("2025-26")
    assert r.fy == "2025-26"


def test_ruleset_invalid_fy_raises():
    with pytest.raises(ValueError, match="No rules found"):
        RuleSet("9999-00")


def test_ruleset_caching(rules):
    meta1 = rules.meta
    meta2 = rules.meta
    assert meta1 is meta2  # same object — cache hit


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


def test_meta_cess_rate(rules):
    assert rules.cess_rate == 0.04


def test_meta_standard_deduction(rules):
    sd = rules.standard_deduction
    assert sd["old"] == 50_000
    assert sd["new"] == 75_000


def test_get_standard_deduction_new(rules):
    assert rules.get_standard_deduction("new") == 75_000


def test_get_standard_deduction_old(rules):
    assert rules.get_standard_deduction("old") == 50_000


# ---------------------------------------------------------------------------
# Slabs
# ---------------------------------------------------------------------------


def test_new_regime_7_slabs(rules):
    assert len(rules.get_slabs("new")) == 7


def test_old_regime_below60_4_slabs(rules):
    assert len(rules.get_slabs("old", "below_60")) == 4


def test_old_regime_senior_4_slabs(rules):
    assert len(rules.get_slabs("old", "senior")) == 4


def test_old_regime_super_senior_3_slabs(rules):
    assert len(rules.get_slabs("old", "super_senior")) == 3


def test_old_regime_unknown_age_fallback(rules):
    """Unknown age_category should fall back to below_60 slabs."""
    fallback = rules.get_slabs("old", "unknown_age")
    below_60 = rules.get_slabs("old", "below_60")
    assert fallback == below_60


# ---------------------------------------------------------------------------
# Rebate 87A
# ---------------------------------------------------------------------------


def test_rebate_87a_new(rules):
    r = rules.get_rebate_87a("new")
    assert r["max_taxable_income"] == 1_200_000
    assert r["max_rebate"] == 60_000


def test_rebate_87a_old(rules):
    r = rules.get_rebate_87a("old")
    assert r["max_taxable_income"] == 500_000
    assert r["max_rebate"] == 12_500


# ---------------------------------------------------------------------------
# Surcharge
# ---------------------------------------------------------------------------


def test_surcharge_tiers_new_3_tiers(rules):
    tiers = rules.get_surcharge_tiers("new")
    assert len(tiers) == 3


def test_surcharge_tiers_old_4_tiers(rules):
    tiers = rules.get_surcharge_tiers("old")
    assert len(tiers) == 4


def test_surcharge_first_tier_new(rules):
    tiers = rules.get_surcharge_tiers("new")
    assert tiers[0]["threshold"] == 5_000_000
    assert tiers[0]["rate"] == 0.10


def test_max_surcharge_rate_new(rules):
    assert rules.get_max_surcharge_rate("new") == 0.25


def test_max_surcharge_rate_old(rules):
    assert rules.get_max_surcharge_rate("old") == 0.37


# ---------------------------------------------------------------------------
# Missing file
# ---------------------------------------------------------------------------


def test_missing_rule_file_raises(rules):
    with pytest.raises(FileNotFoundError):
        rules.load_deduction_rule("nonexistent_section")
