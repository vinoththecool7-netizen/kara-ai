"""Tests for ProfileBuilder — slot management, intent readiness, and tax profile conversion (Task 2 - Day 34)."""
from __future__ import annotations

import pytest

from kara_api.agent.profile_builder import ProfileBuilder
from kara_api.agent.prompts import INTENT_SPECS, Intent
from kara_tax_engine.models import Deductions, TaxProfile


# ---------------------------------------------------------------------------
# TestSlotManagement
# ---------------------------------------------------------------------------
class TestSlotManagement:
    """Verify slot CRUD operations on ProfileBuilder."""

    def test_add_single_slot(self):
        pb = ProfileBuilder()
        pb.add_slot("gross_salary", 1500000)
        assert pb.get_slot("gross_salary") == 1500000

    def test_add_multiple_slots(self):
        pb = ProfileBuilder()
        pb.add_slots({"gross_salary": 1500000, "regime": "new"})
        assert pb.get_slot("gross_salary") == 1500000
        assert pb.get_slot("regime") == "new"

    def test_get_slot_returns_value(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        assert pb.get_slot("gross_salary") == 1500000

    def test_get_slot_returns_none_for_missing(self):
        pb = ProfileBuilder()
        assert pb.get_slot("nonexistent") is None

    def test_add_slot_overwrites_existing(self):
        pb = ProfileBuilder()
        pb.add_slot("gross_salary", 1500000)
        pb.add_slot("gross_salary", 2000000)
        assert pb.get_slot("gross_salary") == 2000000

    def test_get_filled_slots_returns_copy(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        filled = pb.get_filled_slots()
        filled["gross_salary"] = 9999999
        # Original must be untouched
        assert pb.get_slot("gross_salary") == 1500000

    def test_remove_slot(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        pb.remove_slot("gross_salary")
        assert pb.get_slot("gross_salary") is None

    def test_clear_removes_all(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000, "regime": "new"})
        pb.clear()
        assert pb.slot_count == 0
        assert pb.get_slot("gross_salary") is None

    def test_slot_count(self):
        pb = ProfileBuilder()
        assert pb.slot_count == 0
        pb.add_slot("gross_salary", 1500000)
        assert pb.slot_count == 1
        pb.add_slot("regime", "new")
        assert pb.slot_count == 2
        pb.remove_slot("regime")
        assert pb.slot_count == 1

    def test_initial_slots_from_constructor(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        assert pb.get_slot("gross_salary") == 1500000
        assert pb.slot_count == 1


# ---------------------------------------------------------------------------
# TestIntentReadiness
# ---------------------------------------------------------------------------
class TestIntentReadiness:
    """Verify intent readiness checks and missing slot detection."""

    def test_compute_tax_ready_with_salary(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        assert pb.is_intent_ready(Intent.COMPUTE_TAX) is True

    def test_compute_tax_not_ready_empty(self):
        pb = ProfileBuilder()
        assert pb.is_intent_ready(Intent.COMPUTE_TAX) is False

    def test_compare_regimes_ready(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        assert pb.is_intent_ready(Intent.COMPARE_REGIMES) is True

    def test_capital_gains_ready(self):
        pb = ProfileBuilder(initial_slots={
            "asset_class": "listed_equity",
            "purchase_price": 100000,
            "sale_price": 200000,
            "holding_months": 24,
        })
        assert pb.is_intent_ready(Intent.CAPITAL_GAINS) is True

    def test_capital_gains_not_ready_missing_one(self):
        pb = ProfileBuilder(initial_slots={
            "asset_class": "listed_equity",
            "purchase_price": 100000,
            "sale_price": 200000,
            # holding_months missing
        })
        assert pb.is_intent_ready(Intent.CAPITAL_GAINS) is False

    def test_compliance_ready(self):
        pb = ProfileBuilder(initial_slots={
            "income_sources": ["salary"],
            "total_income": 1500000,
        })
        assert pb.is_intent_ready(Intent.COMPLIANCE) is True

    def test_general_query_always_ready(self):
        pb = ProfileBuilder()
        assert pb.is_intent_ready(Intent.GENERAL_QUERY) is True

    def test_get_missing_slots_correct(self):
        pb = ProfileBuilder(initial_slots={"asset_class": "listed_equity"})
        missing = pb.get_missing_slots(Intent.CAPITAL_GAINS)
        assert len(missing) == 3
        assert "purchase_price" in missing
        assert "sale_price" in missing
        assert "holding_months" in missing

    def test_get_ready_intents(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        ready = pb.get_ready_intents()
        assert Intent.COMPUTE_TAX in ready
        assert Intent.COMPARE_REGIMES in ready
        assert Intent.GENERAL_QUERY in ready
        # Capital gains should NOT be ready (missing required fields)
        assert Intent.CAPITAL_GAINS not in ready


# ---------------------------------------------------------------------------
# TestTaxProfileConversion
# ---------------------------------------------------------------------------
class TestTaxProfileConversion:
    """Verify conversion from accumulated slots to TaxProfile."""

    def test_basic_salary_profile(self):
        pb = ProfileBuilder(initial_slots={"gross_salary": 1500000})
        profile = pb.to_tax_profile()
        assert isinstance(profile, TaxProfile)
        assert profile.gross_salary == 1500000

    def test_profile_with_regime_and_age(self):
        pb = ProfileBuilder(initial_slots={
            "gross_salary": 1500000,
            "regime": "old",
            "age_category": "senior",
        })
        profile = pb.to_tax_profile()
        assert profile.regime == "old"
        assert profile.age_category == "senior"

    def test_profile_with_deductions(self):
        pb = ProfileBuilder(initial_slots={
            "gross_salary": 1500000,
            "section_80c": 150000,
            "section_80d": 25000,
        })
        profile = pb.to_tax_profile()
        assert profile.deductions.section_80c == 150000
        assert profile.deductions.section_80d == 25000

    def test_profile_with_hra_exemption(self):
        pb = ProfileBuilder(initial_slots={
            "gross_salary": 1500000,
            "hra_exemption": 120000,
        })
        profile = pb.to_tax_profile()
        assert profile.deductions.hra_exemption == 120000

    def test_profile_with_all_income_types(self):
        pb = ProfileBuilder(initial_slots={
            "gross_salary": 1500000,
            "business_income": 500000,
            "house_property_income": -200000,
            "other_income": 100000,
        })
        profile = pb.to_tax_profile()
        assert profile.gross_salary == 1500000
        assert profile.business_income == 500000
        assert profile.house_property_income == -200000
        assert profile.other_income == 100000

    def test_profile_raises_on_no_income(self):
        pb = ProfileBuilder()
        with pytest.raises(ValueError, match="No income source provided"):
            pb.to_tax_profile()


# ---------------------------------------------------------------------------
# TestSerialization
# ---------------------------------------------------------------------------
class TestSerialization:
    """Verify to_dict / from_dict round-trip."""

    def test_to_dict_roundtrip(self):
        pb = ProfileBuilder(initial_slots={
            "gross_salary": 1500000,
            "regime": "new",
        })
        data = pb.to_dict()
        restored = ProfileBuilder.from_dict(data)
        assert restored.get_slot("gross_salary") == 1500000
        assert restored.get_slot("regime") == "new"

    def test_to_dict_empty(self):
        pb = ProfileBuilder()
        data = pb.to_dict()
        assert data == {"slots": {}}

    def test_from_dict_preserves_values(self):
        original_slots = {
            "gross_salary": 1500000,
            "regime": "old",
            "age_category": "senior",
            "business_income": 500000,
            "house_property_income": -200000,
            "other_income": 100000,
        }
        pb = ProfileBuilder(initial_slots=original_slots)
        data = pb.to_dict()
        restored = ProfileBuilder.from_dict(data)
        for key, value in original_slots.items():
            assert restored.get_slot(key) == value

    def test_from_dict_with_deductions(self):
        pb = ProfileBuilder(initial_slots={
            "gross_salary": 1500000,
            "section_80c": 150000,
            "section_80d": 25000,
            "section_80ccd_1b": 50000,
            "section_24b": 200000,
        })
        data = pb.to_dict()
        restored = ProfileBuilder.from_dict(data)
        assert restored.get_slot("section_80c") == 150000
        assert restored.get_slot("section_80d") == 25000
        assert restored.get_slot("section_80ccd_1b") == 50000
        assert restored.get_slot("section_24b") == 200000
