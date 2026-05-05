"""Tool registry: validates inputs, dispatches to Python functions, returns results."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from kara_api.llm.models import ToolCall

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Result of executing a tool."""

    tool_call_id: str
    name: str
    content: str  # JSON-serialized result or error message
    is_error: bool = False


class ToolExecutionError(Exception):
    """Raised when a tool fails to execute."""

    pass


class ToolRegistry:
    """Registry that maps tool names to handler functions.

    Dependencies injected via constructor for testability.
    """

    def __init__(
        self,
        computer=None,  # TaxComputer instance
        comparator=None,  # RegimeComparator instance
        optimizer=None,  # DeductionOptimizer instance
        cg_calculator=None,  # CapitalGainsCalculator instance
        search_fn=None,  # async search function
        db_session_factory=None,
        embedding_provider=None,
    ):
        from kara_tax_engine import (
            CapitalGainsCalculator,
            DeductionOptimizer,
            RegimeComparator,
            TaxComputer,
        )

        self._computer = computer or TaxComputer(fy="2025-26")
        self._comparator = comparator or RegimeComparator(fy="2025-26")
        self._optimizer = optimizer or DeductionOptimizer(fy="2025-26")
        self._cg_calc = cg_calculator or CapitalGainsCalculator(fy="2025-26")
        self._search_fn = search_fn
        self._db_session_factory = db_session_factory
        self._embedding_provider = embedding_provider

        self._handlers: dict[str, Callable] = {
            "compute_tax": self._handle_compute_tax,
            "compare_regimes": self._handle_compare_regimes,
            "compute_capital_gains": self._handle_compute_capital_gains,
            "find_deduction_gaps": self._handle_find_deduction_gaps,
            "search_tax_law": self._handle_search_tax_law,
            "get_tds_rate": self._handle_get_tds_rate,
            "calculate_advance_tax": self._handle_calculate_advance_tax,
            "select_itr_form": self._handle_select_itr_form,
            "parse_form16": self._handle_parse_form16,
            "parse_ais": self._handle_parse_ais,
            "parse_26as": self._handle_parse_26as,
        }

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        if tool_call.name not in self._handlers:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Unknown tool: {tool_call.name}",
                is_error=True,
            )
        handler = self._handlers[tool_call.name]
        try:
            result = await handler(tool_call.arguments)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=json.dumps(result, default=str),
            )
        except (ValueError, ValidationError) as exc:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Invalid input: {exc}",
                is_error=True,
            )
        except Exception as exc:
            logger.exception("Tool %s execution error", tool_call.name)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"Execution error: {exc}",
                is_error=True,
            )

    async def execute_many(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls sequentially and return results."""
        return [await self.execute(tc) for tc in tool_calls]

    # ------------------------------------------------------------------
    # Handler implementations
    # ------------------------------------------------------------------

    async def _handle_compute_tax(self, args: dict[str, Any]) -> dict[str, Any]:
        """Build TaxProfile from args and compute tax."""
        from kara_tax_engine.models import Deductions, TaxProfile

        profile = self._build_tax_profile(args)
        result = self._computer.compute_from_profile(profile)
        return result.model_dump()

    async def _handle_compare_regimes(self, args: dict[str, Any]) -> dict[str, Any]:
        """Build TaxProfile and compare both regimes."""
        from kara_tax_engine.models import TaxProfile

        # Comparator computes both regimes internally, so regime value doesn't matter
        profile = self._build_tax_profile(args, default_regime="new")
        result = self._comparator.compare(profile)
        return result.model_dump()

    async def _handle_compute_capital_gains(
        self, args: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Compute capital gains for a list of transactions."""
        transactions = args["transactions"]
        results = self._cg_calc.compute_multiple(transactions)
        return [r.model_dump() for r in results]

    async def _handle_find_deduction_gaps(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Build TaxProfile with old regime and optimize deductions."""
        profile = self._build_tax_profile(args, default_regime="old")
        result = self._optimizer.optimize(profile)
        return result.model_dump()

    async def _handle_search_tax_law(
        self, args: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Search the knowledge base using hybrid search."""
        if (
            self._search_fn is None
            or self._db_session_factory is None
            or self._embedding_provider is None
        ):
            return [{"error": "Knowledge base search not configured"}]

        query = args["query"]
        k = args.get("k", 5)

        async with self._db_session_factory() as session:
            results = await self._search_fn(
                query=query,
                k=k,
                session=session,
                provider=self._embedding_provider,
            )
            return [r.model_dump() for r in results]

    async def _handle_get_tds_rate(self, args: dict[str, Any]) -> dict[str, Any]:
        """Look up TDS rate for a payment type (stub)."""
        tds_rates = {
            "salary": {"section": "192", "rate": "as per slab", "threshold": 0},
            "interest": {"section": "194A", "rate": 0.10, "threshold": 40000},
            "rent": {"section": "194I", "rate": 0.10, "threshold": 240000},
            "professional_fees": {
                "section": "194J",
                "rate": 0.10,
                "threshold": 30000,
            },
            "commission": {"section": "194H", "rate": 0.05, "threshold": 15000},
            "dividend": {"section": "194", "rate": 0.10, "threshold": 5000},
            "contractor": {"section": "194C", "rate": 0.02, "threshold": 30000},
        }

        payment_type = args["payment_type"]
        has_pan = args.get("has_pan", True)
        amount = args.get("amount", 0)

        if payment_type not in tds_rates:
            return {
                "error": f"Unknown payment type: {payment_type}",
                "known_types": list(tds_rates.keys()),
            }

        info = dict(tds_rates[payment_type])
        info["payment_type"] = payment_type
        info["amount"] = amount

        if not has_pan:
            info["rate"] = 0.20
            info["note"] = "Higher rate (20%) applied due to missing PAN"

        return info

    async def _handle_calculate_advance_tax(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate advance tax installments (stub)."""
        total_estimated_tax = args["total_estimated_tax"]
        tds_already_deducted = args.get("tds_already_deducted", 0)
        financial_year = args.get("financial_year", "2025-26")

        net = max(0, total_estimated_tax - tds_already_deducted)

        if net < 10000:
            return {
                "advance_tax_required": False,
                "net_tax_after_tds": net,
                "message": "No advance tax required (net tax liability below Rs 10,000)",
            }

        # Parse financial year for due dates
        start_year = int(financial_year.split("-")[0])

        installments = [
            {
                "quarter": "Q1",
                "due_date": f"{start_year}-06-15",
                "percentage": 15,
                "cumulative_percentage": 15,
                "amount": int(net * 0.15),
            },
            {
                "quarter": "Q2",
                "due_date": f"{start_year}-09-15",
                "percentage": 30,
                "cumulative_percentage": 45,
                "amount": int(net * 0.30),
            },
            {
                "quarter": "Q3",
                "due_date": f"{start_year}-12-15",
                "percentage": 30,
                "cumulative_percentage": 75,
                "amount": int(net * 0.30),
            },
            {
                "quarter": "Q4",
                "due_date": f"{start_year + 1}-03-15",
                "percentage": 25,
                "cumulative_percentage": 100,
                "amount": int(net * 0.25),
            },
        ]

        return {
            "advance_tax_required": True,
            "total_estimated_tax": total_estimated_tax,
            "tds_already_deducted": tds_already_deducted,
            "net_tax_after_tds": net,
            "financial_year": financial_year,
            "installments": installments,
        }

    async def _handle_select_itr_form(self, args: dict[str, Any]) -> dict[str, Any]:
        """Determine the appropriate ITR form (stub)."""
        income_sources = args.get("income_sources", [])
        is_company = args.get("is_company", False)
        is_partnership = args.get("is_partnership", False)
        has_foreign_assets = args.get("has_foreign_assets", False)
        is_resident = args.get("is_resident", True)
        total_income = args.get("total_income", 0)

        # Decision tree
        if is_company:
            return {
                "form": "ITR-6",
                "reason": "Companies must file ITR-6",
            }

        if is_partnership:
            return {
                "form": "ITR-5",
                "reason": "Partnership firms must file ITR-5",
            }

        if has_foreign_assets or not is_resident or "foreign_income" in income_sources:
            return {
                "form": "ITR-2",
                "reason": "Required for non-residents, foreign income, or foreign assets",
            }

        if "business" in income_sources:
            # Presumptive taxation (44AD/44ADA) -> ITR-4, else ITR-3
            if total_income <= 5000000:
                return {
                    "form": "ITR-4",
                    "reason": (
                        "Business income eligible for presumptive taxation "
                        "(Section 44AD/44ADA) with total income up to Rs 50L"
                    ),
                }
            return {
                "form": "ITR-3",
                "reason": "Business/professional income above presumptive limits",
            }

        if "capital_gains" in income_sources:
            return {
                "form": "ITR-2",
                "reason": "Capital gains income requires ITR-2",
            }

        # Salary / house property / other sources only
        salary_only_sources = {"salary", "house_property", "other_sources"}
        if set(income_sources).issubset(salary_only_sources):
            if total_income <= 5000000:
                return {
                    "form": "ITR-1",
                    "reason": (
                        "Salary/pension, one house property, and other sources "
                        "with total income up to Rs 50L"
                    ),
                }
            return {
                "form": "ITR-2",
                "reason": "Total income exceeds Rs 50L limit for ITR-1",
            }

        return {
            "form": "ITR-2",
            "reason": "Default form for individuals with multiple income sources",
        }

    async def _handle_parse_form16(self, args: dict[str, Any]) -> dict:
        """Parse a Base64-encoded Form 16 PDF and return structured data."""
        import base64

        from kara_api.parsers import Form16ParseError, parse_form16

        pdf_bytes = base64.b64decode(args["pdf_base64"])
        password = args.get("password")
        try:
            doc = parse_form16(pdf_bytes, password=password)
            return doc.model_dump(mode="json")
        except Form16ParseError as exc:
            raise ValueError(str(exc)) from exc

    async def _handle_parse_ais(self, args: dict[str, Any]) -> dict:
        """Parse a Base64-encoded AIS JSON blob or PDF and return structured data."""
        import base64
        import json

        from kara_api.parsers.ais import parse_ais_json, parse_ais_pdf

        raw_bytes = base64.b64decode(args["content_b64"])
        content_type = args["content_type"]

        if content_type == "json":
            blob = json.loads(raw_bytes.decode("utf-8"))
            doc = parse_ais_json(blob)
        else:
            doc = parse_ais_pdf(raw_bytes)

        return doc.model_dump(mode="json")

    async def _handle_parse_26as(self, args: dict[str, Any]) -> dict:
        """Parse a Base64-encoded Form 26AS PDF and return structured data."""
        import base64

        from kara_api.parsers.twenty_six_as import parse_form_26as

        pdf_bytes = base64.b64decode(args["content_b64"])
        doc = parse_form_26as(pdf_bytes)
        return doc.model_dump(mode="json")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_tax_profile(
        self,
        args: dict[str, Any],
        default_regime: str = "new",
    ):
        """Build a TaxProfile from tool call arguments."""
        from kara_tax_engine.models import Deductions, TaxProfile

        gross_salary = args.get("gross_salary", 0)
        regime = args.get("regime", default_regime)
        age_category = args.get("age_category", "below_60")
        business_income = args.get("business_income", 0)
        house_property_income = args.get("house_property_income", 0)
        other_income = args.get("other_income", 0)

        # Build deductions if provided
        deductions = Deductions()
        if "deductions" in args and args["deductions"]:
            deductions = self._build_deductions(args["deductions"])

        profile = TaxProfile(
            gross_salary=gross_salary,
            regime=regime,
            age_category=age_category,
            business_income=business_income,
            house_property_income=house_property_income,
            other_income=other_income,
            deductions=deductions,
        )
        return profile

    def _build_deductions(self, ded_dict: dict[str, int]) -> "Deductions":
        """Build Deductions from a user-friendly dict (e.g. {"80C": 150000})."""
        from kara_tax_engine.models import Deductions

        mapping = {
            "80C": "section_80c",
            "80c": "section_80c",
            "section_80c": "section_80c",
            "80CCC": "section_80ccc",
            "80CCD1": "section_80ccd_1",
            "80CCD1B": "section_80ccd_1b",
            "80CCD(1B)": "section_80ccd_1b",
            "80ccd_1b": "section_80ccd_1b",
            "section_80ccd_1b": "section_80ccd_1b",
            "80CCD2": "section_80ccd_2",
            "80CCD(2)": "section_80ccd_2",
            "section_80ccd_2": "section_80ccd_2",
            "80D": "section_80d",
            "80d": "section_80d",
            "section_80d": "section_80d",
            "80D_parents": "section_80d_parents",
            "section_80d_parents": "section_80d_parents",
            "80E": "section_80e",
            "section_80e": "section_80e",
            "80G": "section_80g",
            "section_80g": "section_80g",
            "80TTA": "section_80tta",
            "section_80tta": "section_80tta",
            "80TTB": "section_80ttb",
            "section_80ttb": "section_80ttb",
            "80U": "section_80u",
            "section_80u": "section_80u",
            "80DD": "section_80dd",
            "section_80dd": "section_80dd",
            "24b": "section_24b",
            "section_24b": "section_24b",
        }

        ded = Deductions()
        for key, value in ded_dict.items():
            attr = mapping.get(key)
            if attr and hasattr(ded, attr):
                setattr(ded, attr, value)
        return ded
