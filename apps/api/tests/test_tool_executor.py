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
    """get_tds_rate is backed by the FY 2025-26 YAML rate table."""

    @pytest.mark.asyncio
    async def test_salary_is_slab(self, registry):
        tc = _make_tool_call("get_tds_rate", {"payment_type": "salary"})
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["section"] == "192"
        assert data["rate"] is None
        assert data["rate_description"] == "as per slab"

    @pytest.mark.asyncio
    async def test_bank_interest_fa2025_threshold(self, registry):
        tc = _make_tool_call(
            "get_tds_rate", {"payment_type": "interest", "amount": 100000}
        )
        result = await registry.execute(tc)
        data = json.loads(result.content)
        assert data["section"] == "194A"
        assert data["rate"] == 0.10
        assert data["threshold"] == 50000  # FA 2025 (was 40K)
        assert data["applicable"] is True
        assert data["tds_amount"] == 10000

    @pytest.mark.asyncio
    async def test_senior_threshold(self, registry):
        tc = _make_tool_call(
            "get_tds_rate",
            {"payment_type": "interest", "amount": 80000, "is_senior": True},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["threshold"] == 100000
        assert data["applicable"] is False

    @pytest.mark.asyncio
    async def test_no_pan(self, registry):
        tc = _make_tool_call(
            "get_tds_rate", {"payment_type": "interest", "has_pan": False}
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["rate"] == 0.20
        assert "PAN" in data["note"]

    @pytest.mark.asyncio
    async def test_commission_rate_cut(self, registry):
        tc = _make_tool_call("get_tds_rate", {"payment_type": "commission"})
        data = json.loads((await registry.execute(tc)).content)
        assert data["rate"] == 0.02  # cut from 5% effective Oct 2024

    @pytest.mark.asyncio
    async def test_unknown_type_is_error_listing_known_types(self, registry):
        tc = _make_tool_call("get_tds_rate", {"payment_type": "bribes"})
        result = await registry.execute(tc)
        assert result.is_error is True
        assert "professional_fees" in result.content


# ---------------------------------------------------------------------------
# Advance Tax (real scheduler)
# ---------------------------------------------------------------------------


class TestCalculateAdvanceTax:
    @pytest.mark.asyncio
    async def test_quarterly_schedule(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax", {"total_estimated_tax": 200000}
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["required"] is True
        assert [i["cumulative_pct"] for i in data["installments"]] == [15, 45, 75, 100]
        assert [i["quarter"] for i in data["installments"]] == ["Q1", "Q2", "Q3", "Q4"]
        assert data["installments"][0]["due_date"] == "2025-06-15"

    @pytest.mark.asyncio
    async def test_below_10k_not_required(self, registry):
        tc = _make_tool_call("calculate_advance_tax", {"total_estimated_tax": 8000})
        data = json.loads((await registry.execute(tc)).content)
        assert data["required"] is False
        assert "10,000" in data["reason"]

    @pytest.mark.asyncio
    async def test_tds_offset(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax",
            {"total_estimated_tax": 300000, "tds_already_deducted": 250000},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["net_liability"] == 50000
        assert sum(i["amount_due"] for i in data["installments"]) == 50000

    @pytest.mark.asyncio
    async def test_presumptive_single_installment(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax",
            {"total_estimated_tax": 100000, "is_presumptive": True},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert len(data["installments"]) == 1
        assert data["installments"][0]["due_date"] == "2026-03-15"

    @pytest.mark.asyncio
    async def test_senior_exemption(self, registry):
        tc = _make_tool_call(
            "calculate_advance_tax",
            {"total_estimated_tax": 500000, "is_senior_without_business": True},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["required"] is False
        assert "senior" in data["reason"].lower()


# ---------------------------------------------------------------------------
# Interest 234A/B/C (new tool)
# ---------------------------------------------------------------------------


class TestCalculateInterest234:
    @pytest.mark.asyncio
    async def test_234b_and_234c_for_unpaid_advance_tax(self, registry):
        tc = _make_tool_call(
            "calculate_interest_234",
            {
                "total_tax_liability": 100000,
                "tds_deducted": 0,
                "advance_tax_paid": 0,
                "as_of_date": "2026-07-31",
            },
        )
        result = await registry.execute(tc)
        assert result.is_error is False
        data = json.loads(result.content)
        assert data["interest_234b"]["interest"] == 4000  # 4 months x 1% on 100K
        assert data["interest_234c"]["interest"] == 5050
        assert data["total_interest"] == 9050

    @pytest.mark.asyncio
    async def test_234a_when_filed_late(self, registry):
        tc = _make_tool_call(
            "calculate_interest_234",
            {
                "total_tax_liability": 100000,
                "tds_deducted": 0,
                "advance_tax_paid": 100000,
                "filing_date": "2026-09-15",
            },
        )
        data = json.loads((await registry.execute(tc)).content)
        # Fully paid in advance: no 234B/C; unpaid tax is zero so no 234A either
        assert data["total_interest"] == 0

    @pytest.mark.asyncio
    async def test_no_interest_when_fully_paid_on_time(self, registry):
        tc = _make_tool_call(
            "calculate_interest_234",
            {
                "total_tax_liability": 100000,
                "advance_tax_paid": 100000,
                "cumulative_paid": {"q1": 15000, "q2": 45000, "q3": 75000, "q4": 100000},
            },
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["total_interest"] == 0


# ---------------------------------------------------------------------------
# ITR selector (real decision tree)
# ---------------------------------------------------------------------------


class TestSelectItrForm:
    @pytest.mark.asyncio
    async def test_simple_salaried_itr1(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"total_income": 1200000, "has_salary": True},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["form"] == "ITR-1"

    @pytest.mark.asyncio
    async def test_capital_gains_itr2(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"total_income": 2000000, "has_salary": True, "has_other_capital_gains": True},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["form"] == "ITR-2"

    @pytest.mark.asyncio
    async def test_small_112a_ltcg_still_itr1(self, registry):
        """AY 2025-26 change the old stub got wrong: small 112A LTCG fits ITR-1."""
        tc = _make_tool_call(
            "select_itr_form",
            {"total_income": 1200000, "has_salary": True, "ltcg_112a_amount": 100000},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["form"] == "ITR-1"

    @pytest.mark.asyncio
    async def test_presumptive_business_itr4(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"total_income": 2000000, "has_business": True, "is_presumptive": True},
        )
        data = json.loads((await registry.execute(tc)).content)
        assert data["form"] == "ITR-4"

    @pytest.mark.asyncio
    async def test_company_itr6(self, registry):
        tc = _make_tool_call("select_itr_form", {"entity_type": "company"})
        data = json.loads((await registry.execute(tc)).content)
        assert data["form"] == "ITR-6"

    @pytest.mark.asyncio
    async def test_foreign_assets_itr2(self, registry):
        tc = _make_tool_call(
            "select_itr_form",
            {"total_income": 2000000, "has_salary": True, "has_foreign_assets": True},
        )
        data = json.loads((await registry.execute(tc)).content)
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


# ---------------------------------------------------------------------------
# PII masking on parse_* tool results
# ---------------------------------------------------------------------------


class TestParseToolPIIMasking:
    """Parse-tool results are streamed to clients, persisted in
    tool_calls_json, and fed to the LLM — the raw PAN must never appear."""

    @pytest.mark.asyncio
    async def test_parse_form16_masks_pans(self, registry):
        import base64
        import re

        from tests.fixtures.form16_factory import make_form16_standard

        b64 = base64.b64encode(make_form16_standard()).decode()
        result = await registry._handle_parse_form16({"pdf_base64": b64})
        assert re.fullmatch(r"X+[A-Z0-9]{4}", result["part_a"]["employee_pan"])
        assert re.fullmatch(r"X+[A-Z0-9]{4}", result["part_a"]["employer_pan"])
        # The raw text excerpt must not leak the unmasked PANs either.
        excerpt = result.get("raw_text_excerpt") or ""
        assert "ABCDE1234F" not in excerpt
        assert "AABCA1234C" not in excerpt

    @pytest.mark.asyncio
    async def test_parse_form16_execute_content_has_no_raw_pan(self, registry):
        import base64

        from tests.fixtures.form16_factory import make_form16_standard

        b64 = base64.b64encode(make_form16_standard()).decode()
        tc = _make_tool_call("parse_form16", {"pdf_base64": b64})
        tool_result = await registry.execute(tc)
        assert tool_result.is_error is False
        assert "ABCDE1234F" not in tool_result.content
        assert "AABCA1234C" not in tool_result.content

    @pytest.mark.asyncio
    async def test_parse_ais_masks_pan(self, registry):
        import base64

        from tests.fixtures.ais_factory import build_ais_json

        blob = build_ais_json()
        b64 = base64.b64encode(json.dumps(blob).encode()).decode()
        result = await registry._handle_parse_ais(
            {"content_b64": b64, "content_type": "json"}
        )
        assert result["pan"] == "XXXXXX234F"

    @pytest.mark.asyncio
    async def test_parse_26as_masks_pan(self, registry):
        import base64

        from tests.fixtures.twenty_six_as_factory import build_26as_pdf

        b64 = base64.b64encode(build_26as_pdf()).decode()
        result = await registry._handle_parse_26as({"content_b64": b64})
        assert result["pan"] == "XXXXXX234F"
