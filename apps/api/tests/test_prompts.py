"""Tests for system prompt and intent taxonomy (Task 1 - Day 33)."""
from __future__ import annotations

import pytest

from kara_api.agent.prompts import (
    ALL_SLOTS,
    ENHANCED_SYSTEM_PROMPT,
    INTENT_SPECS,
    Intent,
    IntentSpec,
    SlotDefinition,
    get_intent_spec,
    get_required_slots,
    get_slot_definition,
)
from kara_api.tools.schemas import ALL_TOOLS, TOOL_MAP


# ---------------------------------------------------------------------------
# TestIntentEnum
# ---------------------------------------------------------------------------
class TestIntentEnum:
    """Verify Intent enum structure and coverage."""

    def test_intent_count(self):
        assert len(Intent) == 9

    def test_intent_values_are_strings(self):
        for intent in Intent:
            assert isinstance(intent.value, str)
            assert intent.value.isidentifier(), (
                f"Intent value {intent.value!r} is not a valid identifier"
            )

    def test_all_intents_have_specs(self):
        for intent in Intent:
            assert intent in INTENT_SPECS, (
                f"Intent {intent.name} has no entry in INTENT_SPECS"
            )


# ---------------------------------------------------------------------------
# TestSlotDefinitions
# ---------------------------------------------------------------------------
class TestSlotDefinitions:
    """Verify ALL_SLOTS registry."""

    def test_slot_count_minimum(self):
        assert len(ALL_SLOTS) >= 20

    def test_all_slots_have_descriptions(self):
        for name, slot in ALL_SLOTS.items():
            assert slot.description, (
                f"Slot {name!r} has an empty description"
            )

    def test_slot_types_valid(self):
        valid_types = {"int", "str", "float", "bool", "list"}
        for name, slot in ALL_SLOTS.items():
            assert slot.slot_type in valid_types, (
                f"Slot {name!r} has invalid slot_type {slot.slot_type!r}"
            )

    def test_income_slots_present(self):
        assert "gross_salary" in ALL_SLOTS
        assert "business_income" in ALL_SLOTS

    def test_demographic_slots_present(self):
        assert "age_category" in ALL_SLOTS
        assert "residential_status" in ALL_SLOTS


# ---------------------------------------------------------------------------
# TestIntentSpecs
# ---------------------------------------------------------------------------
class TestIntentSpecs:
    """Verify IntentSpec entries for correctness and consistency."""

    def test_compute_tax_required_slots(self):
        spec = INTENT_SPECS[Intent.COMPUTE_TAX]
        assert "gross_salary" in spec.required_slots
        assert spec.primary_tool == "compute_tax"

    def test_capital_gains_required_slots(self):
        spec = INTENT_SPECS[Intent.CAPITAL_GAINS]
        assert spec.required_slots == [
            "asset_class",
            "purchase_price",
            "sale_price",
            "holding_months",
        ]
        assert spec.primary_tool == "compute_capital_gains"

    def test_general_query_no_required(self):
        spec = INTENT_SPECS[Intent.GENERAL_QUERY]
        assert spec.required_slots == []
        assert spec.primary_tool == "search_tax_law"

    def test_all_primary_tools_valid(self):
        for intent, spec in INTENT_SPECS.items():
            if spec.primary_tool is not None:
                assert spec.primary_tool in TOOL_MAP, (
                    f"Intent {intent.name} references unknown tool "
                    f"{spec.primary_tool!r}"
                )

    def test_all_required_slots_exist(self):
        for intent, spec in INTENT_SPECS.items():
            for slot_name in spec.required_slots:
                assert slot_name in ALL_SLOTS, (
                    f"Intent {intent.name} requires unknown slot "
                    f"{slot_name!r}"
                )

    def test_all_optional_slots_exist(self):
        for intent, spec in INTENT_SPECS.items():
            for slot_name in spec.optional_slots:
                assert slot_name in ALL_SLOTS, (
                    f"Intent {intent.name} has unknown optional slot "
                    f"{slot_name!r}"
                )

    def test_each_intent_has_examples(self):
        for intent, spec in INTENT_SPECS.items():
            assert len(spec.example_queries) >= 1, (
                f"Intent {intent.name} has no example_queries"
            )


# ---------------------------------------------------------------------------
# TestEnhancedSystemPrompt
# ---------------------------------------------------------------------------
class TestEnhancedSystemPrompt:
    """Verify the system prompt content."""

    def test_prompt_is_nonempty(self):
        assert len(ENHANCED_SYSTEM_PROMPT) > 100

    def test_prompt_mentions_kara(self):
        assert "Kara" in ENHANCED_SYSTEM_PROMPT

    def test_prompt_mentions_tools(self):
        tool_names = [t.name for t in ALL_TOOLS]
        found = [name for name in tool_names if name in ENHANCED_SYSTEM_PROMPT]
        assert len(found) >= 3, (
            f"System prompt mentions only {len(found)} tools: {found}. "
            f"Expected at least 3."
        )


# ---------------------------------------------------------------------------
# TestHelperFunctions
# ---------------------------------------------------------------------------
class TestHelperFunctions:
    """Verify convenience helper functions."""

    def test_get_intent_spec_valid(self):
        spec = get_intent_spec(Intent.COMPUTE_TAX)
        assert isinstance(spec, IntentSpec)
        assert spec.intent == Intent.COMPUTE_TAX

    def test_get_required_slots(self):
        slots = get_required_slots(Intent.COMPUTE_TAX)
        assert isinstance(slots, list)
        assert slots == INTENT_SPECS[Intent.COMPUTE_TAX].required_slots

    def test_get_slot_definition_unknown(self):
        result = get_slot_definition("nonexistent_slot")
        assert result is None
