"""Tool schemas for the Kara AI agent.

Defines 8 ToolDefinition constants in OpenAI function-calling JSON Schema
format.  These describe every tool the agent is allowed to invoke during a
conversation.
"""
from __future__ import annotations

from kara_api.llm.models import ToolDefinition

# ---------------------------------------------------------------------------
# 1. COMPUTE_TAX
# ---------------------------------------------------------------------------
COMPUTE_TAX = ToolDefinition(
    name="compute_tax",
    description=(
        "Compute Indian income tax for a taxpayer. Returns a full breakdown "
        "with slab details, deductions, surcharge, cess, and effective rate."
    ),
    parameters={
        "type": "object",
        "properties": {
            "gross_salary": {
                "type": "integer",
                "description": "Annual gross salary in INR.",
            },
            "regime": {
                "type": "string",
                "enum": ["old", "new"],
                "description": "Tax regime to compute under.",
            },
            "age_category": {
                "type": "string",
                "enum": ["below_60", "senior", "super_senior"],
                "description": "Age bracket of the taxpayer.",
            },
            "business_income": {
                "type": "integer",
                "default": 0,
                "description": "Income from business or profession in INR.",
            },
            "house_property_income": {
                "type": "integer",
                "default": 0,
                "description": "Income (or loss) from house property in INR.",
            },
            "other_income": {
                "type": "integer",
                "default": 0,
                "description": "Income from other sources in INR.",
            },
            "deductions": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
                "description": (
                    "Map of deduction section codes to claimed amounts, "
                    "e.g. {\"80C\": 150000, \"80D\": 25000}."
                ),
            },
        },
        "required": ["gross_salary"],
    },
)

# ---------------------------------------------------------------------------
# 2. COMPARE_REGIMES
# ---------------------------------------------------------------------------
COMPARE_REGIMES = ToolDefinition(
    name="compare_regimes",
    description=(
        "Compare old vs new tax regime for a taxpayer. Returns tax under "
        "both regimes, recommended regime, savings amount, and breakeven "
        "deduction level."
    ),
    parameters={
        "type": "object",
        "properties": {
            "gross_salary": {
                "type": "integer",
                "description": "Annual gross salary in INR.",
            },
            "age_category": {
                "type": "string",
                "enum": ["below_60", "senior", "super_senior"],
                "description": "Age bracket of the taxpayer.",
            },
            "business_income": {
                "type": "integer",
                "default": 0,
                "description": "Income from business or profession in INR.",
            },
            "house_property_income": {
                "type": "integer",
                "default": 0,
                "description": "Income (or loss) from house property in INR.",
            },
            "other_income": {
                "type": "integer",
                "default": 0,
                "description": "Income from other sources in INR.",
            },
            "deductions": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
                "description": (
                    "Map of deduction section codes to claimed amounts, "
                    "e.g. {\"80C\": 150000, \"80D\": 25000}."
                ),
            },
        },
        "required": ["gross_salary"],
    },
)

# ---------------------------------------------------------------------------
# 3. COMPUTE_CAPITAL_GAINS
# ---------------------------------------------------------------------------
COMPUTE_CAPITAL_GAINS = ToolDefinition(
    name="compute_capital_gains",
    description=(
        "Compute capital gains tax on one or more asset transactions."
    ),
    parameters={
        "type": "object",
        "properties": {
            "transactions": {
                "type": "array",
                "description": "List of asset sale transactions.",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_class": {
                            "type": "string",
                            "enum": [
                                "listed_equity",
                                "equity_mf",
                                "debt_mf",
                                "property",
                                "gold",
                                "unlisted_shares",
                                "vda_crypto",
                            ],
                            "description": "Type of asset sold.",
                        },
                        "purchase_price": {
                            "type": "integer",
                            "description": "Purchase price in INR.",
                        },
                        "sale_price": {
                            "type": "integer",
                            "description": "Sale price in INR.",
                        },
                        "holding_months": {
                            "type": "integer",
                            "description": "Number of months the asset was held.",
                        },
                        "fmv_31jan2018": {
                            "type": "integer",
                            "description": (
                                "Fair market value as on 31 Jan 2018 "
                                "(for grandfathering, optional)."
                            ),
                        },
                        "section_54_amount": {
                            "type": "integer",
                            "default": 0,
                            "description": (
                                "Amount claimed under section 54 exemption."
                            ),
                        },
                        "section_54ec_amount": {
                            "type": "integer",
                            "default": 0,
                            "description": (
                                "Amount claimed under section 54EC exemption."
                            ),
                        },
                    },
                    "required": [
                        "asset_class",
                        "purchase_price",
                        "sale_price",
                        "holding_months",
                    ],
                },
            },
        },
        "required": ["transactions"],
    },
)

# ---------------------------------------------------------------------------
# 4. FIND_DEDUCTION_GAPS
# ---------------------------------------------------------------------------
FIND_DEDUCTION_GAPS = ToolDefinition(
    name="find_deduction_gaps",
    description=(
        "Analyze current deductions and suggest tax-saving opportunities."
    ),
    parameters={
        "type": "object",
        "properties": {
            "gross_salary": {
                "type": "integer",
                "description": "Annual gross salary in INR.",
            },
            "age_category": {
                "type": "string",
                "enum": ["below_60", "senior", "super_senior"],
                "description": "Age bracket of the taxpayer.",
            },
            "deductions": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
                "description": (
                    "Map of deduction section codes to claimed amounts."
                ),
            },
            "business_income": {
                "type": "integer",
                "default": 0,
                "description": "Income from business or profession in INR.",
            },
            "house_property_income": {
                "type": "integer",
                "default": 0,
                "description": "Income (or loss) from house property in INR.",
            },
            "other_income": {
                "type": "integer",
                "default": 0,
                "description": "Income from other sources in INR.",
            },
        },
        "required": ["gross_salary"],
    },
)

# ---------------------------------------------------------------------------
# 5. SEARCH_TAX_LAW
# ---------------------------------------------------------------------------
SEARCH_TAX_LAW = ToolDefinition(
    name="search_tax_law",
    description=(
        "Search the Indian Income Tax Act knowledge base using hybrid search."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query.",
            },
            "k": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
                "description": "Number of results to return.",
            },
        },
        "required": ["query"],
    },
)

# ---------------------------------------------------------------------------
# 6. GET_TDS_RATE (stub)
# ---------------------------------------------------------------------------
GET_TDS_RATE = ToolDefinition(
    name="get_tds_rate",
    description="Look up TDS rate for a payment type.",
    parameters={
        "type": "object",
        "properties": {
            "payment_type": {
                "type": "string",
                "description": "Type of payment (e.g. salary, rent, professional).",
            },
            "amount": {
                "type": "integer",
                "description": "Payment amount in INR.",
            },
            "has_pan": {
                "type": "boolean",
                "default": True,
                "description": "Whether the payee has a valid PAN.",
            },
        },
        "required": ["payment_type"],
    },
)

# ---------------------------------------------------------------------------
# 7. CALCULATE_ADVANCE_TAX (stub)
# ---------------------------------------------------------------------------
CALCULATE_ADVANCE_TAX = ToolDefinition(
    name="calculate_advance_tax",
    description="Calculate advance tax installments and due dates.",
    parameters={
        "type": "object",
        "properties": {
            "total_estimated_tax": {
                "type": "integer",
                "description": "Total estimated tax liability for the year in INR.",
            },
            "tds_already_deducted": {
                "type": "integer",
                "default": 0,
                "description": "TDS already deducted during the year in INR.",
            },
            "financial_year": {
                "type": "string",
                "default": "2025-26",
                "description": "Financial year in YYYY-YY format.",
            },
        },
        "required": ["total_estimated_tax"],
    },
)

# ---------------------------------------------------------------------------
# 8. SELECT_ITR_FORM (stub)
# ---------------------------------------------------------------------------
SELECT_ITR_FORM = ToolDefinition(
    name="select_itr_form",
    description="Determine which ITR form the taxpayer should file.",
    parameters={
        "type": "object",
        "properties": {
            "income_sources": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "salary",
                        "house_property",
                        "business",
                        "capital_gains",
                        "other_sources",
                        "foreign_income",
                        "agricultural",
                    ],
                },
                "description": "List of income source types for the taxpayer.",
            },
            "is_resident": {
                "type": "boolean",
                "default": True,
                "description": "Whether the taxpayer is a resident of India.",
            },
            "has_foreign_assets": {
                "type": "boolean",
                "default": False,
                "description": "Whether the taxpayer holds foreign assets.",
            },
            "total_income": {
                "type": "integer",
                "description": "Total income in INR.",
            },
            "is_company": {
                "type": "boolean",
                "default": False,
                "description": "Whether the taxpayer is a company.",
            },
            "is_partnership": {
                "type": "boolean",
                "default": False,
                "description": "Whether the taxpayer is a partnership firm.",
            },
        },
        "required": ["income_sources", "total_income"],
    },
)

# ---------------------------------------------------------------------------
# 9. PARSE_FORM16
# ---------------------------------------------------------------------------
PARSE_FORM16 = ToolDefinition(
    name="parse_form16",
    description=(
        "Parse an uploaded Form 16 PDF (Part A + Part B) and return structured "
        "employer, TDS, salary, deductions, and tax fields."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pdf_base64": {
                "type": "string",
                "description": "Base64-encoded PDF bytes.",
            },
            "password": {
                "type": "string",
                "description": "Optional PDF password.",
            },
        },
        "required": ["pdf_base64"],
    },
)

# ---------------------------------------------------------------------------
# Convenience exports
# ---------------------------------------------------------------------------
ALL_TOOLS: list[ToolDefinition] = [
    COMPUTE_TAX,
    COMPARE_REGIMES,
    COMPUTE_CAPITAL_GAINS,
    FIND_DEDUCTION_GAPS,
    SEARCH_TAX_LAW,
    GET_TDS_RATE,
    CALCULATE_ADVANCE_TAX,
    SELECT_ITR_FORM,
    PARSE_FORM16,
]

TOOL_MAP: dict[str, ToolDefinition] = {t.name: t for t in ALL_TOOLS}
