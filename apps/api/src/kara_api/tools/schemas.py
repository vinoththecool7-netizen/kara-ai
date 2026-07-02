"""Tool schemas for the Kara AI agent.

Defines the ToolDefinition constants in OpenAI function-calling JSON Schema
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
                "properties": {
                    "parents_senior": {
                        "type": "boolean",
                        "description": (
                            "Set true only if the parents covered under "
                            "80D_parents are aged 60+, which raises that cap "
                            "from 25,000 to 50,000. Ask the user if unknown."
                        ),
                    },
                },
                "additionalProperties": {"type": "integer"},
                "description": (
                    "Map of deduction section codes to claimed amounts, "
                    "e.g. {\"80C\": 150000, \"80D\": 25000}. For 80G enter the "
                    "eligible deduction amount (after the 50%/100% category and "
                    "qualifying limit), not the raw donation."
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
                "properties": {
                    "parents_senior": {
                        "type": "boolean",
                        "description": (
                            "Set true only if the parents covered under "
                            "80D_parents are aged 60+, which raises that cap "
                            "from 25,000 to 50,000. Ask the user if unknown."
                        ),
                    },
                },
                "additionalProperties": {"type": "integer"},
                "description": (
                    "Map of deduction section codes to claimed amounts, "
                    "e.g. {\"80C\": 150000, \"80D\": 25000}. For 80G enter the "
                    "eligible deduction amount (after the 50%/100% category and "
                    "qualifying limit), not the raw donation."
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
# 6. GET_TDS_RATE — FY 2025-26 rate table
# ---------------------------------------------------------------------------
GET_TDS_RATE = ToolDefinition(
    name="get_tds_rate",
    description=(
        "Look up the TDS section, rate, and threshold for a payment type from "
        "the FY 2025-26 rate table; optionally computes the TDS amount."
    ),
    parameters={
        "type": "object",
        "properties": {
            "payment_type": {
                "type": "string",
                "enum": [
                    "salary",
                    "epf_withdrawal",
                    "interest_securities",
                    "dividend",
                    "interest_bank",
                    "interest_other",
                    "lottery",
                    "horse_race",
                    "contractor_individual",
                    "contractor_other",
                    "insurance_commission",
                    "commission",
                    "rent_plant_machinery",
                    "rent_land_building",
                    "property_purchase",
                    "rent_by_individual",
                    "professional_fees",
                    "technical_fees",
                    "mutual_fund_income",
                    "land_acquisition",
                    "ecommerce",
                    "goods_purchase",
                    "vda_transfer",
                ],
                "description": "Nature of the payment.",
            },
            "amount": {
                "type": "integer",
                "description": "Payment amount in INR (enables TDS amount computation).",
            },
            "has_pan": {
                "type": "boolean",
                "default": True,
                "description": "False applies the 20% no-PAN rate under s.206AA.",
            },
            "is_senior": {
                "type": "boolean",
                "default": False,
                "description": "Recipient is a senior citizen (raises 194A threshold to 1L).",
            },
        },
        "required": ["payment_type"],
    },
)

# ---------------------------------------------------------------------------
# 7. CALCULATE_ADVANCE_TAX — s.208/211 schedule
# ---------------------------------------------------------------------------
CALCULATE_ADVANCE_TAX = ToolDefinition(
    name="calculate_advance_tax",
    description=(
        "Build the advance tax installment schedule (15/45/75/100% cumulative "
        "by Jun/Sep/Dec/Mar 15) for the estimated liability."
    ),
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
            "is_presumptive": {
                "type": "boolean",
                "default": False,
                "description": "44AD/44ADA taxpayers pay 100% in one installment by 15 March.",
            },
            "is_senior_without_business": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Resident senior citizen (60+) with no business income — "
                    "exempt from advance tax under s.207(2)."
                ),
            },
        },
        "required": ["total_estimated_tax"],
    },
)

# ---------------------------------------------------------------------------
# 7b. CALCULATE_INTEREST_234 — late payment/filing interest
# ---------------------------------------------------------------------------
CALCULATE_INTEREST_234 = ToolDefinition(
    name="calculate_interest_234",
    description=(
        "Compute interest under s.234A (late filing), s.234B (advance tax "
        "below 90% of assessed tax), and s.234C (installment deferment)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "total_tax_liability": {
                "type": "integer",
                "description": "Assessed/estimated total tax for the year in INR.",
            },
            "tds_deducted": {
                "type": "integer",
                "default": 0,
                "description": "TDS/TCS already deducted in INR.",
            },
            "advance_tax_paid": {
                "type": "integer",
                "default": 0,
                "description": "Total advance tax paid during the year in INR.",
            },
            "filing_date": {
                "type": "string",
                "description": "Actual/planned return filing date (YYYY-MM-DD).",
            },
            "as_of_date": {
                "type": "string",
                "description": "Date up to which 234B interest runs (YYYY-MM-DD).",
            },
            "cumulative_paid": {
                "type": "object",
                "properties": {
                    "q1": {"type": "integer"},
                    "q2": {"type": "integer"},
                    "q3": {"type": "integer"},
                    "q4": {"type": "integer"},
                },
                "description": (
                    "Cumulative advance tax paid by each installment due date "
                    "(15 Jun/Sep/Dec/Mar). Needed for an accurate 234C figure."
                ),
            },
            "is_presumptive": {
                "type": "boolean",
                "default": False,
                "description": "44AD/44ADA: only the 15 March installment is checked.",
            },
            "financial_year": {
                "type": "string",
                "default": "2025-26",
                "description": "Financial year in YYYY-YY format.",
            },
        },
        "required": ["total_tax_liability"],
    },
)

# ---------------------------------------------------------------------------
# 8. SELECT_ITR_FORM — decision tree
# ---------------------------------------------------------------------------
SELECT_ITR_FORM = ToolDefinition(
    name="select_itr_form",
    description=(
        "Recommend the correct ITR form (ITR-1 to ITR-7) for AY 2026-27 from "
        "the taxpayer's situation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": ["individual", "huf", "firm", "llp", "company", "trust"],
                "default": "individual",
                "description": "Type of taxpayer entity.",
            },
            "residential_status": {
                "type": "string",
                "enum": ["resident", "rnor", "non_resident"],
                "default": "resident",
                "description": "Residential status for the year.",
            },
            "total_income": {
                "type": "integer",
                "description": "Total income in INR.",
            },
            "has_salary": {"type": "boolean", "default": False},
            "house_property_count": {
                "type": "integer",
                "default": 0,
                "description": "Number of house properties with income/loss.",
            },
            "has_business": {
                "type": "boolean",
                "default": False,
                "description": "Has business or professional income.",
            },
            "is_presumptive": {
                "type": "boolean",
                "default": False,
                "description": "Business income under 44AD/44ADA/44AE.",
            },
            "ltcg_112a_amount": {
                "type": "integer",
                "default": 0,
                "description": (
                    "LTCG on listed equity u/s 112A in INR (up to 1.25L is "
                    "allowed in ITR-1/ITR-4 from AY 2025-26)."
                ),
            },
            "has_other_capital_gains": {
                "type": "boolean",
                "default": False,
                "description": "Any capital gains other than small 112A LTCG.",
            },
            "has_foreign_assets": {"type": "boolean", "default": False},
            "has_crypto_income": {"type": "boolean", "default": False},
            "is_director": {
                "type": "boolean",
                "default": False,
                "description": "Director of a company (excludes ITR-1/ITR-4).",
            },
            "has_unlisted_shares": {"type": "boolean", "default": False},
            "agricultural_income": {"type": "integer", "default": 0},
        },
        "required": ["total_income"],
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
# 10. PARSE_AIS
# ---------------------------------------------------------------------------
PARSE_AIS = ToolDefinition(
    name="parse_ais",
    description=(
        "Parse an AIS (Annual Information Statement) JSON blob or PDF and return "
        "structured income, TDS, and transaction data."
    ),
    parameters={
        "type": "object",
        "properties": {
            "content_b64": {
                "type": "string",
                "description": "Base64-encoded content (JSON or PDF bytes).",
            },
            "content_type": {
                "type": "string",
                "enum": ["json", "pdf"],
                "description": "Type of content.",
            },
        },
        "required": ["content_b64", "content_type"],
    },
)

# ---------------------------------------------------------------------------
# 11. PARSE_26AS
# ---------------------------------------------------------------------------
PARSE_26AS = ToolDefinition(
    name="parse_26as",
    description=(
        "Parse a Form 26AS (Tax Credit Statement) PDF and return TDS, "
        "advance tax, and refund data."
    ),
    parameters={
        "type": "object",
        "properties": {
            "content_b64": {
                "type": "string",
                "description": "Base64-encoded PDF bytes.",
            },
        },
        "required": ["content_b64"],
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
    CALCULATE_INTEREST_234,
    SELECT_ITR_FORM,
    PARSE_FORM16,
    PARSE_AIS,
    PARSE_26AS,
]

TOOL_MAP: dict[str, ToolDefinition] = {t.name: t for t in ALL_TOOLS}
