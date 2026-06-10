"""Tests for tool schema definitions (Task 6)."""
from __future__ import annotations

import pytest

from kara_api.tools.schemas import (
    ALL_TOOLS,
    CALCULATE_ADVANCE_TAX,
    COMPARE_REGIMES,
    COMPUTE_CAPITAL_GAINS,
    COMPUTE_TAX,
    FIND_DEDUCTION_GAPS,
    GET_TDS_RATE,
    SEARCH_TAX_LAW,
    SELECT_ITR_FORM,
    TOOL_MAP,
)


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------
class TestToolSchemaStructure:
    """Verify overall shape and consistency of the tool catalogue."""

    def test_all_tools_count(self):
        assert len(ALL_TOOLS) == 11

    def test_tool_map_keys(self):
        expected_names = {
            "compute_tax",
            "compare_regimes",
            "compute_capital_gains",
            "find_deduction_gaps",
            "search_tax_law",
            "get_tds_rate",
            "calculate_advance_tax",
            "select_itr_form",
            "parse_form16",
            "parse_ais",
            "parse_26as",
        }
        assert set(TOOL_MAP.keys()) == expected_names

    def test_each_tool_has_name_description_parameters(self):
        for tool in ALL_TOOLS:
            assert tool.name, f"Tool missing name: {tool}"
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.parameters, f"Tool {tool.name} missing parameters"

    def test_parameters_are_valid_json_schema(self):
        for tool in ALL_TOOLS:
            params = tool.parameters
            assert params.get("type") == "object", (
                f"{tool.name}: parameters.type must be 'object'"
            )
            assert "properties" in params, (
                f"{tool.name}: parameters must have 'properties'"
            )
            assert "required" in params, (
                f"{tool.name}: parameters must have 'required'"
            )

    def test_no_duplicate_tool_names(self):
        names = [t.name for t in ALL_TOOLS]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Per-tool required-field tests
# ---------------------------------------------------------------------------
class TestIndividualTools:
    """Validate required fields and enum values for each tool."""

    def test_compute_tax_required_fields(self):
        assert COMPUTE_TAX.parameters["required"] == ["gross_salary"]

    def test_compare_regimes_required_fields(self):
        assert COMPARE_REGIMES.parameters["required"] == ["gross_salary"]

    def test_capital_gains_required_fields(self):
        assert COMPUTE_CAPITAL_GAINS.parameters["required"] == ["transactions"]

    def test_search_tax_law_required_fields(self):
        assert SEARCH_TAX_LAW.parameters["required"] == ["query"]

    def test_find_deduction_gaps_required_fields(self):
        assert FIND_DEDUCTION_GAPS.parameters["required"] == ["gross_salary"]

    def test_get_tds_rate_required_fields(self):
        assert GET_TDS_RATE.parameters["required"] == ["payment_type"]

    def test_advance_tax_required_fields(self):
        assert CALCULATE_ADVANCE_TAX.parameters["required"] == [
            "total_estimated_tax"
        ]

    def test_select_itr_form_required_fields(self):
        assert SELECT_ITR_FORM.parameters["required"] == [
            "income_sources",
            "total_income",
        ]

    def test_capital_gains_transaction_schema(self):
        items = (
            COMPUTE_CAPITAL_GAINS.parameters["properties"]["transactions"]["items"]
        )
        assert set(items["required"]) == {
            "asset_class",
            "purchase_price",
            "sale_price",
            "holding_months",
        }

    def test_regime_enum_values(self):
        regime_prop = COMPUTE_TAX.parameters["properties"]["regime"]
        assert regime_prop["enum"] == ["old", "new"]

    def test_asset_class_enum_values(self):
        items = (
            COMPUTE_CAPITAL_GAINS.parameters["properties"]["transactions"]["items"]
        )
        asset_enum = items["properties"]["asset_class"]["enum"]
        expected = [
            "listed_equity",
            "equity_mf",
            "debt_mf",
            "property",
            "gold",
            "unlisted_shares",
            "vda_crypto",
        ]
        assert asset_enum == expected
