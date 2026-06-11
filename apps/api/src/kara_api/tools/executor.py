"""Tool registry: validates inputs, dispatches to Python functions, returns results."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kara_tax_engine.models import Deductions

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
            AdvanceTaxCalculator,
            CapitalGainsCalculator,
            DeductionOptimizer,
            ITRSelector,
            RegimeComparator,
            TaxComputer,
            TDSCalculator,
        )

        self._computer = computer or TaxComputer(fy="2025-26")
        self._comparator = comparator or RegimeComparator(fy="2025-26")
        self._optimizer = optimizer or DeductionOptimizer(fy="2025-26")
        self._cg_calc = cg_calculator or CapitalGainsCalculator(fy="2025-26")
        self._tds = TDSCalculator(fy="2025-26")
        self._advance_tax = AdvanceTaxCalculator(fy="2025-26")
        self._itr = ITRSelector(fy="2025-26")
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
            "calculate_interest_234": self._handle_calculate_interest_234,
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

        profile = self._build_tax_profile(args)
        result = self._computer.compute_from_profile(profile)
        return result.model_dump()

    async def _handle_compare_regimes(self, args: dict[str, Any]) -> dict[str, Any]:
        """Build TaxProfile and compare both regimes."""

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
        """Look up TDS rate from the FY 2025-26 rate table."""
        result = self._tds.lookup(
            args["payment_type"],
            amount=args.get("amount"),
            has_pan=args.get("has_pan", True),
            is_senior=args.get("is_senior", False),
        )
        return result.model_dump()

    async def _handle_calculate_advance_tax(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the advance tax installment schedule (s.208/211)."""
        schedule = self._advance_tax.schedule(
            total_estimated_tax=args["total_estimated_tax"],
            tds_deducted=args.get("tds_already_deducted", 0),
            is_presumptive=args.get("is_presumptive", False),
            is_senior_without_business=args.get("is_senior_without_business", False),
        )
        return schedule.model_dump(mode="json")

    async def _handle_calculate_interest_234(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute interest under sections 234A, 234B, and 234C."""
        from datetime import date

        from kara_tax_engine import interest_234a, interest_234b, interest_234c

        fy = args.get("financial_year", "2025-26")
        start_year = int(fy.split("-")[0])
        total_tax = args["total_tax_liability"]
        tds = args.get("tds_deducted", 0)
        advance_paid = args.get("advance_tax_paid", 0)

        due_date = date(start_year + 1, 7, 31)  # non-audit individual due date
        filing_date = (
            date.fromisoformat(args["filing_date"]) if args.get("filing_date") else due_date
        )
        as_of = (
            date.fromisoformat(args["as_of_date"]) if args.get("as_of_date") else filing_date
        )

        unpaid = max(0, total_tax - tds - advance_paid)
        r_234a = interest_234a(unpaid, due_date=due_date, filing_date=filing_date)
        r_234b = interest_234b(
            assessed_tax=total_tax,
            tds_deducted=tds,
            advance_tax_paid=advance_paid,
            until=as_of,
            fy=fy,
        )
        # Without per-quarter data, assume the total advance tax was paid
        # evenly available by each due date only if explicitly provided.
        cumulative_paid = args.get("cumulative_paid") or {
            "q1": advance_paid,
            "q2": advance_paid,
            "q3": advance_paid,
            "q4": advance_paid,
        }
        r_234c = interest_234c(
            total_tax_liability=total_tax,
            tds_deducted=tds,
            cumulative_paid=cumulative_paid,
            fy=fy,
            is_presumptive=args.get("is_presumptive", False),
        )

        return {
            "financial_year": fy,
            "interest_234a": r_234a.model_dump(),
            "interest_234b": r_234b.model_dump(),
            "interest_234c": r_234c.model_dump(),
            "total_interest": r_234a.interest + r_234b.interest + r_234c.interest,
        }

    async def _handle_select_itr_form(self, args: dict[str, Any]) -> dict[str, Any]:
        """Recommend the correct ITR form via the decision tree."""
        # Back-compat mapping for older argument shapes
        if args.get("is_company"):
            args.setdefault("entity_type", "company")
        if args.get("is_partnership"):
            args.setdefault("entity_type", "firm")
        sources = args.get("income_sources") or []
        if "business" in sources:
            args.setdefault("has_business", True)
        if "capital_gains" in sources:
            args.setdefault("has_other_capital_gains", True)
        if "foreign_income" in sources:
            args.setdefault("has_foreign_assets", True)
        if "salary" in sources:
            args.setdefault("has_salary", True)

        recommendation = self._itr.select(
            entity_type=args.get("entity_type", "individual"),
            residential_status=args.get("residential_status", "resident"),
            total_income=args.get("total_income", 0),
            has_salary=args.get("has_salary", False),
            house_property_count=args.get("house_property_count", 0),
            has_business=args.get("has_business", False),
            is_presumptive=args.get("is_presumptive", False),
            ltcg_112a_amount=args.get("ltcg_112a_amount", 0),
            has_other_capital_gains=args.get("has_other_capital_gains", False),
            has_foreign_assets=args.get("has_foreign_assets", False),
            has_crypto_income=args.get("has_crypto_income", False),
            is_director=args.get("is_director", False),
            has_unlisted_shares=args.get("has_unlisted_shares", False),
            agricultural_income=args.get("agricultural_income", 0),
        )
        return recommendation.model_dump()

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

    def _build_deductions(self, ded_dict: dict[str, int]) -> Deductions:
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
            if key == "parents_senior":
                ded.parents_senior = bool(value)
                continue
            attr = mapping.get(key)
            if attr and hasattr(ded, attr):
                setattr(ded, attr, value)
        return ded
