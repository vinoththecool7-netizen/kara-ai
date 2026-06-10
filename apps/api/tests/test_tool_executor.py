"""Tests for the ToolRegistry executor — ~24 tests covering all 8 handlers."""
from __future__ import annotations

import json

import pytest

from kara_api.llm.models import ToolCall
from kara_api.tools.executor import ToolRegistry


@pytest.fixture
def registry():
    """Instantiate ToolRegistry with default tax engine singletons (no search deps)."""
    return ToolRegistry()


def _make_tool_call(name: str, arguments: dict, call_id: str = "call_1") -> ToolCall:
    """Helper to build a ToolCall."""
    return ToolCall(id=call_id, name=name, arguments=arguments)


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


class TestToolRegistryUnknown:
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, registry):
        tc = _make_tool_call("nonexistent_tool", {})
        result = await registry.execute(tc)
        assert result.is_error is True
        assert "Unknown tool" in result.content
        assert result.name == "nonexistent_tool"
        assert result.tool_call_id == "call_1"


# ---------------------------------------------------------------------------
# Full implementations
# ---------------------------------------------------------------------------


class TestComputeTax:
    @pytest.mark.asyncio
    async def test_execute_compute_tax(self, registry):
        tc = _make_tool_call("compute_tax", {"gross_salary": 1500000})
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert "taxable_income" in data
        assert "total_tax_payable" in data
        assert "slab_breakdown" in data
        assert data["gross_salary"] == 1500000

    @pytest.mark.asyncio
    async def test_execute_compute_tax_with_deductions(self, registry):
        tc = _make_tool_call(
            "compute_tax",
            {
                "gross_salary": 1500000,
                "regime": "old",
                "deductions": {"80C": 150000, "80D": 25000},
            },
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["total_deductions"] > 0
        assert len(data["deductions_applied"]) > 0

    @pytest.mark.asyncio
    async def test_execute_compute_tax_defaults(self, registry):
        """Missing optionals should use defaults (regime=new, age=below_60, etc.)."""
        tc = _make_tool_call("compute_tax", {"gross_salary": 800000})
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["regime"] == "new"
        assert data["age_category"] == "below_60"

    @pytest.mark.asyncio
    async def test_execute_compute_tax_parents_senior_flag(self, registry):
        """parents_senior in the deductions dict raises the 80D parents cap to 50K."""
        base_args = {
            "gross_salary": 1500000,
            "regime": "old",
            "deductions": {"80D_parents": 50000},
        }
        result_default = await registry.execute(_make_tool_call("compute_tax", base_args))
        data_default = json.loads(result_default.content)
        entry = next(d for d in data_default["deductions_applied"] if d["section"] == "80D")
        assert entry["allowed"] == 25000  # conservative cap without the flag

        senior_args = {
            "gross_salary": 1500000,
            "regime": "old",
            "deductions": {"80D_parents": 50000, "parents_senior": True},
        }
        result_senior = await registry.execute(_make_tool_call("compute_tax", senior_args))
        data_senior = json.loads(result_senior.content)
        entry = next(d for d in data_senior["deductions_applied"] if d["section"] == "80D")
        assert entry["allowed"] == 50000


class TestCompareRegimes:
    @pytest.mark.asyncio
    async def test_execute_compare_regimes(self, registry):
        tc = _make_tool_call(
            "compare_regimes",
            {"gross_salary": 1500000, "deductions": {"80C": 150000}},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert "old_regime" in data
        assert "new_regime" in data
        assert "recommended_regime" in data
        assert "savings" in data
        assert "breakeven_deductions" in data


class TestCapitalGains:
    @pytest.mark.asyncio
    async def test_execute_capital_gains(self, registry):
        tc = _make_tool_call(
            "compute_capital_gains",
            {
                "transactions": [
                    {
                        "asset_class": "listed_equity",
                        "purchase_price": 100000,
                        "sale_price": 250000,
                        "holding_months": 18,
                    }
                ]
            },
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["asset_class"] == "listed_equity"
        assert data[0]["total_gain"] == 150000


class TestFindDeductionGaps:
    @pytest.mark.asyncio
    async def test_execute_find_deduction_gaps(self, registry):
        tc = _make_tool_call(
            "find_deduction_gaps",
            {"gross_salary": 1500000},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert "current_tax" in data
        assert "optimized_tax" in data
        assert "total_potential_saving" in data
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearchTaxLaw:
    @pytest.mark.asyncio
    async def test_execute_search_tax_law_not_configured(self, registry):
        """When search deps are missing, should return error dict."""
        tc = _make_tool_call("search_tax_law", {"query": "section 80C"})
        result = await registry.execute(tc)
        assert result.is_error is False  # Returns data, not an execution error
        data = json.loads(result.content)
        assert isinstance(data, list)
        assert len(data) == 1
        assert "error" in data[0]
        assert "not configured" in data[0]["error"]


# ---------------------------------------------------------------------------
# Stubs — TDS Rate
# ---------------------------------------------------------------------------


class TestGetTdsRate:
    @pytest.mark.asyncio
    async def test_execute_get_tds_rate_salary(self, registry):
        tc = _make_tool_call("get_tds_rate", {"payment_type": "salary"})
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["section"] == "192"
        assert data["rate"] == "as per slab"

    @pytest.mark.asyncio
    async def test_execute_get_tds_rate_interest(self, registry):
        tc = _make_tool_call(
            "get_tds_rate", {"payment_type": "interest", "amount": 100000}
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["section"] == "194A"
        assert data["rate"] == 0.10
        assert data["threshold"] == 40000

    @pytest.mark.asyncio
    async def test_execute_get_tds_rate_no_pan(self, registry):
        tc = _make_tool_call(
            "get_tds_rate",
            {"payment_type": "interest", "has_pan": False},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["rate"] == 0.20
        assert "note" in data
        assert "20%" in data["note"]

    @pytest.mark.asyncio
    async def test_execute_get_tds_rate_unknown_type(self, registry):
        tc = _make_tool_call("get_tds_rate", {"payment_type": "crypto_payment"})
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert "error" in data
        assert "known_types" in data
        assert "salary" in data["known_types"]
        assert "rent" in data["known_types"]


# ---------------------------------------------------------------------------
# Stubs — Advance Tax
# ---------------------------------------------------------------------------


class TestCalculateAdvanceTax:
    @pytest.mark.asyncio
    async def test_execute_advance_tax_basic(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax", {"total_estimated_tax": 200000}
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["advance_tax_required"] is True
        assert len(data["installments"]) == 4
        # Check installment percentages
        pcts = [inst["percentage"] for inst in data["installments"]]
        assert pcts == [15, 30, 30, 25]
        # Check quarter labels
        quarters = [inst["quarter"] for inst in data["installments"]]
        assert quarters == ["Q1", "Q2", "Q3", "Q4"]

    @pytest.mark.asyncio
    async def test_execute_advance_tax_below_10k(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax", {"total_estimated_tax": 8000}
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["advance_tax_required"] is False
        assert "No advance tax" in data["message"]

    @pytest.mark.asyncio
    async def test_execute_advance_tax_with_tds_offset(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax",
            {"total_estimated_tax": 300000, "tds_already_deducted": 250000},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["net_tax_after_tds"] == 50000
        assert data["advance_tax_required"] is True
        # Total of installment amounts should equal net
        total_installments = sum(inst["amount"] for inst in data["installments"])
        # Allow small rounding difference (floor of percentages)
        assert abs(total_installments - 50000) <= 4


# ---------------------------------------------------------------------------
# Stubs — ITR Form
# ---------------------------------------------------------------------------


class TestSelectItrForm:
    @pytest.mark.asyncio
    async def test_execute_select_itr_form_salary(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"income_sources": ["salary"], "total_income": 1200000},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["form"] == "ITR-1"

    @pytest.mark.asyncio
    async def test_execute_select_itr_form_capital_gains(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"income_sources": ["salary", "capital_gains"], "total_income": 2000000},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["form"] == "ITR-2"

    @pytest.mark.asyncio
    async def test_execute_select_itr_form_business(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"income_sources": ["business"], "total_income": 3000000},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["form"] in ("ITR-3", "ITR-4")

    @pytest.mark.asyncio
    async def test_execute_select_itr_form_company(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"income_sources": ["business"], "total_income": 10000000, "is_company": True},
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["form"] == "ITR-6"

    @pytest.mark.asyncio
    async def test_execute_select_itr_form_foreign(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {
                "income_sources": ["salary", "foreign_income"],
                "total_income": 2000000,
                "has_foreign_assets": True,
            },
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["form"] == "ITR-2"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_execute_validation_error(self, registry):
        """Bad input should return is_error=True."""
        tc = _make_tool_call(
            "compute_capital_gains",
            {"transactions": [{"asset_class": "invalid_class", "purchase_price": 100}]},
        )
        result = await registry.execute(tc)
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_execute_many(self, registry):
        """execute_many should process multiple tool calls."""
        calls = [
            _make_tool_call("compute_tax", {"gross_salary": 1000000}, call_id="c1"),
            _make_tool_call("get_tds_rate", {"payment_type": "rent"}, call_id="c2"),
        ]
        results = await registry.execute_many(calls)
        assert len(results) == 2
        assert results[0].tool_call_id == "c1"
        assert results[1].tool_call_id == "c2"
        assert results[0].is_error is False
        assert results[1].is_error is False

    @pytest.mark.asyncio
    async def test_result_content_is_json(self, registry):
        """Successful results should have JSON-parseable content."""
        tc = _make_tool_call("compute_tax", {"gross_salary": 500000})
        result = await registry.execute(tc)
        assert result.is_error is False
        parsed = json.loads(result.content)
        assert isinstance(parsed, dict)
