"""AIS (Annual Information Statement) parser.

Supports two entry points:
    parse_ais_json(blob: dict) -> AISDocument
    parse_ais_pdf(pdf_bytes: bytes) -> AISDocument

AIS JSON structure wraps data in either:
    blob["AIS_Data"]
or
    blob["Annual_Information_Statement"]["AIS_Data"]

Each item has an ``Information_Category`` (e.g. "SFT-005", "194A") and a
``Transaction_Data`` list.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

from kara_api.parsers._common import (
    BaseParsedDocument,
    ParserWarning,
    extract_tables_pages,
    extract_text_pages,
    normalize_cell,
    parse_assessment_year,
    parse_date_flexible,
    parse_pan,
    parse_tan,
    to_paise,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class InterestEntry(BaseModel):
    payer_name: str = ""
    payer_tan: str | None = None
    account_type: Literal["savings", "fd", "rd", "other"] = "other"
    amount: int = 0  # paise
    tds_deducted: int = 0


class DividendEntry(BaseModel):
    payer_name: str = ""
    payer_pan_or_tan: str | None = None
    isin: str | None = None
    amount: int = 0
    tds_deducted: int = 0


class SecurityTxn(BaseModel):
    isin: str | None = None
    scrip_name: str = ""
    txn_type: Literal["buy", "sell"]
    quantity: int = 0
    value: int = 0  # paise
    txn_date: date | None = None
    broker_name: str = ""


class MutualFundTxn(BaseModel):
    scheme_name: str = ""
    folio: str | None = None
    txn_type: Literal["purchase", "redemption", "switch"]
    units: int = 0  # units * 1000 (3 decimal places)
    amount: int = 0  # paise
    txn_date: date | None = None


class RentReceivedEntry(BaseModel):
    tenant_name: str = ""
    tenant_tan: str | None = None
    amount: int = 0
    tds_deducted: int = 0


class SalaryReportedEntry(BaseModel):
    deductor_name: str = ""
    deductor_tan: str | None = None
    amount_paid: int = 0
    tds_deducted: int = 0


class BusinessReceiptEntry(BaseModel):
    payer_name: str = ""
    gstin: str | None = None
    nature_of_payment: str = ""
    amount: int = 0
    tds_deducted: int = 0


class ForeignRemittanceEntry(BaseModel):
    purpose_code: str = ""
    beneficiary: str = ""
    country: str = ""
    amount: int = 0  # paise (foreign amount converted at rate)
    lrs_used: int = 0  # paise


class GSTTurnoverEntry(BaseModel):
    gstin: str = ""
    period_label: str = ""
    taxable_turnover: int = 0
    total_turnover: int = 0


class SFTEntry(BaseModel):
    reporting_entity: str = ""
    transaction_type: str = ""
    amount: int = 0
    info_code: str = ""


class RefundEntry(BaseModel):
    assessment_year: str = ""
    amount: int = 0
    interest: int = 0


class TDSCollectedEntry(BaseModel):
    deductor_name: str = ""
    deductor_tan: str | None = None
    section: str = ""
    amount_paid: int = 0
    tds_amount: int = 0


class TCSEntry(BaseModel):
    collector_name: str = ""
    collector_tan: str | None = None
    section: str = ""
    amount: int = 0
    tcs: int = 0


class PurchaseOfImmovablePropertyEntry(BaseModel):
    buyer_name: str = ""
    seller_name: str = ""
    address: str = ""
    amount: int = 0
    sft_code: str = ""


class AISTotals(BaseModel):
    total_interest: int = 0
    total_dividends: int = 0
    total_salary_reported: int = 0
    total_tds_collected: int = 0
    total_capital_gains_value: int = 0


class AISDocument(BaseParsedDocument):
    name: str = ""
    interest_savings: list[InterestEntry] = []
    interest_fd: list[InterestEntry] = []
    dividends: list[DividendEntry] = []
    security_sales: list[SecurityTxn] = []
    security_purchases: list[SecurityTxn] = []
    mutual_fund_purchases: list[MutualFundTxn] = []
    mutual_fund_redemptions: list[MutualFundTxn] = []
    rent_received: list[RentReceivedEntry] = []
    salary_reported: list[SalaryReportedEntry] = []
    business_receipts: list[BusinessReceiptEntry] = []
    foreign_remittances: list[ForeignRemittanceEntry] = []
    gst_turnover: list[GSTTurnoverEntry] = []
    sft_transactions: list[SFTEntry] = []
    refunds: list[RefundEntry] = []
    tds_collected: list[TDSCollectedEntry] = []
    totals: AISTotals = AISTotals()


# ---------------------------------------------------------------------------
# Internal: totals computation
# ---------------------------------------------------------------------------


def _compute_totals(doc: AISDocument) -> None:
    """Populate doc.totals from the parsed lists in-place."""
    doc.totals = AISTotals(
        total_interest=sum(e.amount for e in doc.interest_savings)
        + sum(e.amount for e in doc.interest_fd),
        total_dividends=sum(e.amount for e in doc.dividends),
        total_salary_reported=sum(e.amount_paid for e in doc.salary_reported),
        total_tds_collected=sum(e.tds_amount for e in doc.tds_collected)
        + sum(e.tds_deducted for e in doc.salary_reported)
        + sum(e.tds_deducted for e in doc.interest_savings)
        + sum(e.tds_deducted for e in doc.interest_fd)
        + sum(e.tds_deducted for e in doc.dividends),
        total_capital_gains_value=sum(e.value for e in doc.security_sales)
        + sum(e.amount for e in doc.mutual_fund_redemptions),
    )


# ---------------------------------------------------------------------------
# Internal: per-category JSON handlers
# ---------------------------------------------------------------------------


def _g(txn: dict, *keys: str, default: Any = "") -> Any:
    """Get the first existing key from a transaction dict."""
    for k in keys:
        if k in txn:
            return txn[k]
    return default


def _paise_field(txn: dict, *keys: str) -> int:
    raw = _g(txn, *keys, default=0)
    if raw == "" or raw is None:
        return 0
    return to_paise(raw)


def _handle_salary(txn: dict, doc: AISDocument) -> None:
    entry = SalaryReportedEntry(
        deductor_name=str(_g(txn, "Deductor_Name", "Employer_Name", "Name")),
        deductor_tan=parse_tan(str(_g(txn, "TAN", "Deductor_TAN", ""))),
        amount_paid=_paise_field(txn, "Amount_Paid", "Salary_Amount", "Amount"),
        tds_deducted=_paise_field(txn, "TDS_Amount", "Tax_Deducted", "TDS"),
    )
    doc.salary_reported.append(entry)


def _handle_interest(txn: dict, doc: AISDocument) -> None:
    raw_type = str(_g(txn, "Account_Type", "Interest_Type", "")).lower()
    if "fd" in raw_type or "fixed" in raw_type or "term" in raw_type:
        acct_type: Literal["savings", "fd", "rd", "other"] = "fd"
    elif "rd" in raw_type or "recurring" in raw_type:
        acct_type = "rd"
    elif "savings" in raw_type or "sav" in raw_type:
        acct_type = "savings"
    else:
        acct_type = "other"

    entry = InterestEntry(
        payer_name=str(_g(txn, "Payer_Name", "Bank_Name", "Name")),
        payer_tan=parse_tan(str(_g(txn, "TAN", "Payer_TAN", ""))),
        account_type=acct_type,
        amount=_paise_field(txn, "Interest_Amount", "Amount"),
        tds_deducted=_paise_field(txn, "TDS_Amount", "Tax_Deducted", "TDS"),
    )
    # Route to the correct list based on account type
    if acct_type == "fd" or acct_type == "rd":
        doc.interest_fd.append(entry)
    else:
        doc.interest_savings.append(entry)


def _handle_dividend(txn: dict, doc: AISDocument) -> None:
    tan_or_pan_raw = str(_g(txn, "TAN", "PAN", "Payer_TAN", ""))
    doc.dividends.append(
        DividendEntry(
            payer_name=str(_g(txn, "Payer_Name", "Company_Name", "Name")),
            payer_pan_or_tan=tan_or_pan_raw if tan_or_pan_raw else None,
            isin=str(_g(txn, "ISIN", "")) or None,
            amount=_paise_field(txn, "Dividend_Amount", "Amount"),
            tds_deducted=_paise_field(txn, "TDS_Amount", "Tax_Deducted", "TDS"),
        )
    )


def _handle_security_sale(txn: dict, doc: AISDocument) -> None:
    doc.security_sales.append(
        SecurityTxn(
            isin=str(_g(txn, "ISIN", "")) or None,
            scrip_name=str(_g(txn, "Scrip_Name", "Company_Name", "Name")),
            txn_type="sell",
            quantity=int(_g(txn, "Quantity", 0) or 0),
            value=_paise_field(txn, "Sale_Value", "Amount", "Transaction_Amount"),
            txn_date=parse_date_flexible(str(_g(txn, "Transaction_Date", "Date", ""))),
            broker_name=str(_g(txn, "Broker_Name", "Intermediary_Name", "")),
        )
    )


def _handle_security_purchase(txn: dict, doc: AISDocument) -> None:
    doc.security_purchases.append(
        SecurityTxn(
            isin=str(_g(txn, "ISIN", "")) or None,
            scrip_name=str(_g(txn, "Scrip_Name", "Company_Name", "Name")),
            txn_type="buy",
            quantity=int(_g(txn, "Quantity", 0) or 0),
            value=_paise_field(txn, "Purchase_Value", "Amount", "Transaction_Amount"),
            txn_date=parse_date_flexible(str(_g(txn, "Transaction_Date", "Date", ""))),
            broker_name=str(_g(txn, "Broker_Name", "Intermediary_Name", "")),
        )
    )


def _handle_mf_purchase(txn: dict, doc: AISDocument) -> None:
    units_raw = _g(txn, "Units", "Units_Purchased", 0)
    try:
        units_int = int(float(str(units_raw)) * 1000)
    except (ValueError, TypeError):
        units_int = 0

    doc.mutual_fund_purchases.append(
        MutualFundTxn(
            scheme_name=str(_g(txn, "Scheme_Name", "Fund_Name", "Name")),
            folio=str(_g(txn, "Folio_Number", "Folio", "")) or None,
            txn_type="purchase",
            units=units_int,
            amount=_paise_field(txn, "Amount", "Purchase_Amount"),
            txn_date=parse_date_flexible(str(_g(txn, "Transaction_Date", "Date", ""))),
        )
    )


def _handle_mf_redemption(txn: dict, doc: AISDocument) -> None:
    units_raw = _g(txn, "Units", "Units_Redeemed", 0)
    try:
        units_int = int(float(str(units_raw)) * 1000)
    except (ValueError, TypeError):
        units_int = 0

    doc.mutual_fund_redemptions.append(
        MutualFundTxn(
            scheme_name=str(_g(txn, "Scheme_Name", "Fund_Name", "Name")),
            folio=str(_g(txn, "Folio_Number", "Folio", "")) or None,
            txn_type="redemption",
            units=units_int,
            amount=_paise_field(txn, "Amount", "Redemption_Amount"),
            txn_date=parse_date_flexible(str(_g(txn, "Transaction_Date", "Date", ""))),
        )
    )


def _handle_rent(txn: dict, doc: AISDocument) -> None:
    doc.rent_received.append(
        RentReceivedEntry(
            tenant_name=str(_g(txn, "Tenant_Name", "Deductor_Name", "Name")),
            tenant_tan=parse_tan(str(_g(txn, "TAN", "Tenant_TAN", ""))),
            amount=_paise_field(txn, "Rent_Amount", "Amount"),
            tds_deducted=_paise_field(txn, "TDS_Amount", "Tax_Deducted", "TDS"),
        )
    )


def _handle_business_receipt(txn: dict, doc: AISDocument) -> None:
    doc.business_receipts.append(
        BusinessReceiptEntry(
            payer_name=str(_g(txn, "Payer_Name", "Deductor_Name", "Name")),
            gstin=str(_g(txn, "GSTIN", "")) or None,
            nature_of_payment=str(_g(txn, "Nature_Of_Payment", "Payment_Type", "")),
            amount=_paise_field(txn, "Amount_Paid", "Amount"),
            tds_deducted=_paise_field(txn, "TDS_Amount", "Tax_Deducted", "TDS"),
        )
    )


def _handle_foreign_remittance(txn: dict, doc: AISDocument) -> None:
    doc.foreign_remittances.append(
        ForeignRemittanceEntry(
            purpose_code=str(_g(txn, "Purpose_Code", "LRS_Purpose", "")),
            beneficiary=str(_g(txn, "Beneficiary_Name", "Beneficiary", "")),
            country=str(_g(txn, "Country", "Destination_Country", "")),
            amount=_paise_field(txn, "Amount", "Remittance_Amount"),
            lrs_used=_paise_field(txn, "LRS_Amount_Used", "LRS_Limit_Used", 0),
        )
    )


def _handle_gst_turnover(txn: dict, doc: AISDocument) -> None:
    doc.gst_turnover.append(
        GSTTurnoverEntry(
            gstin=str(_g(txn, "GSTIN", "")),
            period_label=str(_g(txn, "Period", "Tax_Period", "")),
            taxable_turnover=_paise_field(txn, "Taxable_Turnover", "Taxable_Value"),
            total_turnover=_paise_field(txn, "Total_Turnover", "Gross_Turnover"),
        )
    )


def _handle_immovable_property(txn: dict, doc: AISDocument) -> None:
    # SFT-006: purchase/sale of immovable property — mapped to sft_transactions
    doc.sft_transactions.append(
        SFTEntry(
            reporting_entity=str(_g(txn, "Reporting_Entity", "Registrar", "Name")),
            transaction_type="purchase_immovable_property",
            amount=_paise_field(txn, "Property_Value", "Amount", "Transaction_Amount"),
            info_code="SFT-006",
        )
    )


def _handle_sft_high_value(txn: dict, doc: AISDocument) -> None:
    doc.sft_transactions.append(
        SFTEntry(
            reporting_entity=str(_g(txn, "Reporting_Entity", "Institution_Name", "Name")),
            transaction_type=str(_g(txn, "Transaction_Type", "SFT_Type", "")),
            amount=_paise_field(txn, "Amount", "Transaction_Amount"),
            info_code=str(_g(txn, "SFT_Code", "Info_Code", "SFT-001")),
        )
    )


def _handle_refund(txn: dict, doc: AISDocument) -> None:
    doc.refunds.append(
        RefundEntry(
            assessment_year=str(_g(txn, "Assessment_Year", "AY", "")),
            amount=_paise_field(txn, "Refund_Amount", "Amount"),
            interest=_paise_field(txn, "Refund_Interest", "Interest_Amount", 0),
        )
    )


def _handle_other_tds(txn: dict, doc: AISDocument) -> None:
    doc.tds_collected.append(
        TDSCollectedEntry(
            deductor_name=str(_g(txn, "Deductor_Name", "Name")),
            deductor_tan=parse_tan(str(_g(txn, "TAN", "Deductor_TAN", ""))),
            section=str(_g(txn, "Section_Code", "TDS_Section", "")),
            amount_paid=_paise_field(txn, "Amount_Paid", "Amount"),
            tds_amount=_paise_field(txn, "TDS_Amount", "Tax_Deducted", "TDS"),
        )
    )


# ---------------------------------------------------------------------------
# Category dispatch table
# ---------------------------------------------------------------------------

# Maps category code → handler function(txn: dict, doc: AISDocument) -> None
_CATEGORY_DISPATCH: dict[str, Callable[[dict, AISDocument], None]] = {
    "192": _handle_salary,
    "TDS-SALARY": _handle_salary,
    "194A": _handle_interest,
    "SFT-016": _handle_interest,
    "194": _handle_dividend,
    "SFT-011": _handle_security_sale,
    "SALE-SECURITIES": _handle_security_sale,
    "SFT-012": _handle_security_purchase,
    "PURCHASE-SECURITIES": _handle_security_purchase,
    "SFT-013": _handle_mf_purchase,
    "MF-PURCHASE": _handle_mf_purchase,
    "SFT-014": _handle_mf_redemption,
    "MF-REDEMPTION": _handle_mf_redemption,
    "194I": _handle_rent,
    "TDS-RENT": _handle_rent,
    "194J": _handle_business_receipt,
    "194C": _handle_business_receipt,
    "LRS": _handle_foreign_remittance,
    "FOREIGN-REMITTANCE": _handle_foreign_remittance,
    "GSTR": _handle_gst_turnover,
    "GST-TURNOVER": _handle_gst_turnover,
    "SFT-006": _handle_immovable_property,
    "IMMOVABLE-PROPERTY": _handle_immovable_property,
    "SFT-001": _handle_sft_high_value,
    "SFT-HIGH-VALUE": _handle_sft_high_value,
    "INCOME-TAX-REFUND": _handle_refund,
    "REFUND": _handle_refund,
    "OTHER-TDS": _handle_other_tds,
}


# ---------------------------------------------------------------------------
# JSON entry point
# ---------------------------------------------------------------------------


def parse_ais_json(blob: dict) -> AISDocument:
    """Parse an AIS JSON blob and return a structured AISDocument.

    The JSON may be wrapped under:
        blob["AIS_Data"]
    or:
        blob["Annual_Information_Statement"]["AIS_Data"]

    Parameters
    ----------
    blob:
        Raw dict from json.loads() of the AIS download.
    """
    doc = AISDocument(source="json")

    # --- Extract PAN and AY from top-level keys ---
    for key in ("PAN", "Taxpayer_PAN", "pan"):
        if key in blob and blob[key]:
            doc.pan = str(blob[key]).strip() or None
            break

    for key in ("Assessment_Year", "AY", "assessment_year"):
        if key in blob and blob[key]:
            doc.assessment_year = parse_assessment_year(str(blob[key])) or str(blob[key])
            break

    for key in ("Name", "Taxpayer_Name", "name"):
        if key in blob and blob[key]:
            doc.name = str(blob[key]).strip()
            break

    # --- Locate AIS_Data list ---
    ais_data: list[dict] | None = None
    if "AIS_Data" in blob:
        ais_data = blob["AIS_Data"]
    elif "Annual_Information_Statement" in blob:
        inner = blob["Annual_Information_Statement"]
        if isinstance(inner, dict) and "AIS_Data" in inner:
            ais_data = inner["AIS_Data"]
            # Also pick up PAN/AY from inner if not already found
            if not doc.pan:
                doc.pan = inner.get("PAN") or inner.get("Taxpayer_PAN")
            if not doc.assessment_year:
                ay_raw = inner.get("Assessment_Year") or inner.get("AY", "")
                doc.assessment_year = parse_assessment_year(str(ay_raw)) or ay_raw or None
            if not doc.name:
                doc.name = str(inner.get("Name", "") or "")

    if ais_data is None:
        doc.warnings.append(
            ParserWarning(
                code="no_ais_data",
                message="Could not locate AIS_Data key in the JSON blob.",
            )
        )
        return doc

    # --- Dispatch each category ---
    for item in ais_data:
        if not isinstance(item, dict):
            continue

        code = str(
            item.get("Information_Category")
            or item.get("Category_Code")
            or item.get("Category")
            or ""
        ).strip()

        transactions: list[dict] = item.get("Transaction_Data") or []
        if isinstance(transactions, dict):
            transactions = [transactions]

        handler = _CATEGORY_DISPATCH.get(code)
        if handler is None:
            doc.warnings.append(
                ParserWarning(
                    code="unknown_category",
                    message=f"Unrecognized AIS category: {code}",
                    location=f"AIS_Data[{code}]",
                )
            )
            continue

        for txn in transactions:
            if not isinstance(txn, dict):
                continue
            try:
                handler(txn, doc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("AIS JSON handler error for category %s: %s", code, exc)
                doc.warnings.append(
                    ParserWarning(
                        code="handler_error",
                        message=f"Error processing {code} transaction: {exc}",
                        location=f"AIS_Data[{code}]",
                    )
                )

    _compute_totals(doc)
    return doc


# ---------------------------------------------------------------------------
# PDF entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Portal-layout PDF parsing (real e-filing AIS downloads)
# ---------------------------------------------------------------------------
#
# The portal PDF has no "Information Category:" text markers. Every item is
# a summary row under a header like:
#     SR. NO. | INFORMATION CODE | INFORMATION DESCRIPTION |
#     INFORMATION SOURCE | COUNT | AMOUNT
# usually followed by a category-specific detail table (savings-interest
# accounts, per-transaction security sales, quarterly MF purchases, ...).
# Summary and detail rows may share one extracted table or span tables and
# pages, so state carries across the whole row stream. Cells are mapped by
# raw column index taken from the most recent header row — extracted tables
# pad with empty columns, but data rows share their header's geometry.


class _PortalItem:
    """The active summary row's context while its detail rows stream in."""

    def __init__(self, category: str, code: str, desc: str, source: str, amount: int):
        self.category = category
        self.code = code
        self.desc = desc
        self.source = source
        self.amount = amount  # paise, from the summary row
        self.had_details = False


def _portal_category(code: str, desc: str) -> str:
    c, d = code.upper(), desc.lower()
    if "(SB)" in c or ("interest" in d and "saving" in d):
        return "interest_savings"
    if "interest" in d and ("deposit" in d or "term" in d or "(td)" in c.lower()):
        return "interest_fd"
    if "dividend" in d:
        return "dividend"
    if "-EMF" in c or "equity oriented mutual fund" in d:
        return "sale_emf"
    if "-OTU" in c or d.startswith("sale of"):
        return "sale_otu"
    if "purchase of mutual fund" in d:
        return "purchase_mf"
    if d.startswith("purchase of"):
        return "purchase_sec"
    if "salary" in d:
        return "salary"
    return "other"


def _find_col(headers: list[str], *needles: str) -> int | None:
    """Index of the first header cell containing every needle (case-blind)."""
    for idx, cell in enumerate(headers):
        up = cell.upper()
        if all(n in up for n in needles):
            return idx
    return None


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


def _flush_portal_item(item: _PortalItem | None, doc: AISDocument) -> None:
    """Emit a summary-level entry for items whose detail rows never came."""
    if item is None or item.had_details:
        return
    cat, src, amt = item.category, item.source, item.amount
    if cat == "interest_savings":
        doc.interest_savings.append(
            InterestEntry(payer_name=src, account_type="savings", amount=amt)
        )
    elif cat == "interest_fd":
        doc.interest_fd.append(
            InterestEntry(payer_name=src, account_type="fd", amount=amt)
        )
    elif cat == "dividend":
        doc.dividends.append(DividendEntry(payer_name=src, amount=amt))
    elif cat == "sale_emf":
        doc.mutual_fund_redemptions.append(
            MutualFundTxn(txn_type="redemption", scheme_name=src, amount=amt)
        )
    elif cat == "sale_otu":
        doc.security_sales.append(
            SecurityTxn(txn_type="sell", broker_name=src, value=amt)
        )
    elif cat == "purchase_mf":
        doc.mutual_fund_purchases.append(
            MutualFundTxn(txn_type="purchase", scheme_name=src, amount=amt)
        )
    elif cat == "purchase_sec":
        doc.security_purchases.append(
            SecurityTxn(txn_type="buy", broker_name=src, value=amt)
        )
    elif cat == "salary":
        doc.salary_reported.append(
            SalaryReportedEntry(deductor_name=src, amount_paid=amt)
        )
    else:
        doc.sft_transactions.append(
            SFTEntry(
                reporting_entity=src,
                transaction_type=item.desc,
                amount=amt,
                info_code=item.code,
            )
        )


def _portal_detail_entry(
    item: _PortalItem, kind: str, cols: dict[str, int | None], row: list[str], doc: AISDocument
) -> bool:
    """Append one detail-row entry for the active item; True when added."""
    if kind == "interest":
        amount = to_paise(_cell(row, cols.get("amount")))
        if amount == 0:
            return False
        acct = _cell(row, cols.get("acct_type")).lower()
        acct_type = (
            "savings" if "sav" in acct
            else "fd" if ("term" in acct or "fixed" in acct)
            else "fd" if item.category == "interest_fd"
            else "savings" if item.category == "interest_savings"
            else "other"
        )
        target = doc.interest_fd if acct_type == "fd" else doc.interest_savings
        target.append(
            InterestEntry(payer_name=item.source, account_type=acct_type, amount=amount)
        )
        return True

    if kind == "sale":
        amount = to_paise(_cell(row, cols.get("consideration")))
        if amount == 0:
            return False
        txn_date = parse_date_flexible(_cell(row, cols.get("date")))
        name = _cell(row, cols.get("name")) or item.source
        qty_raw = _cell(row, cols.get("qty")).replace(",", "")
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = 0.0
        if item.category == "sale_emf":
            doc.mutual_fund_redemptions.append(
                MutualFundTxn(
                    txn_type="redemption",
                    scheme_name=name,
                    units=int(round(qty * 1000)),
                    amount=amount,
                    txn_date=txn_date,
                )
            )
        else:
            doc.security_sales.append(
                SecurityTxn(
                    txn_type="sell",
                    scrip_name=name,
                    quantity=int(qty),
                    value=amount,
                    txn_date=txn_date,
                    broker_name=item.source,
                )
            )
        return True

    if kind == "purchase":
        amount = to_paise(_cell(row, cols.get("amount")))
        if amount == 0:
            return False
        if item.category == "purchase_mf":
            doc.mutual_fund_purchases.append(
                MutualFundTxn(
                    txn_type="purchase",
                    scheme_name=_cell(row, cols.get("scheme")) or item.source,
                    amount=amount,
                )
            )
        else:
            doc.security_purchases.append(
                SecurityTxn(txn_type="buy", value=amount, broker_name=item.source)
            )
        return True

    return False


def _parse_portal_tables(
    pages_tables: list[list[list[list[str | None]]]], doc: AISDocument
) -> bool:
    """Parse portal-layout tables into *doc*; True when any item was found."""
    mode: str | None = None  # "summary" | detail kind
    summary_cols: dict[str, int | None] = {}
    detail_cols: dict[str, int | None] = {}
    item: _PortalItem | None = None
    found = False

    for page_tables in pages_tables:
        for table in page_tables:
            for raw_row in table or []:
                row = [normalize_cell(c) for c in raw_row]
                joined = " ".join(row).upper()
                if not joined.strip():
                    continue

                if "NO TRANSACTIONS PRESENT" in joined:
                    continue

                if "INFORMATION CODE" in joined and "AMOUNT" in joined:
                    summary_cols = {
                        "code": _find_col(row, "INFORMATION CODE"),
                        "desc": _find_col(row, "INFORMATION DESCRIPTION"),
                        "source": _find_col(row, "INFORMATION SOURCE"),
                        "amount": _find_col(row, "AMOUNT"),
                    }
                    mode = "summary"
                    continue

                if "INTEREST AMOUNT" in joined and "ACCOUNT" in joined:
                    detail_cols = {
                        "amount": _find_col(row, "INTEREST AMOUNT"),
                        "acct_type": _find_col(row, "ACCOUNT TYPE"),
                    }
                    mode = "interest"
                    continue

                if "SALES CONSIDERATION" in joined and "QUANTITY" in joined:
                    detail_cols = {
                        "date": _find_col(row, "DATE OF SALE"),
                        "name": _find_col(row, "SECURITY NAME"),
                        "qty": _find_col(row, "QUANTITY"),
                        "consideration": _find_col(row, "SALES CONSIDERATION"),
                    }
                    mode = "sale"
                    continue

                if "QUARTER" in joined and "PURCHASE" in joined:
                    detail_cols = {
                        "amount": _find_col(row, "PURCHASE AMOUNT")
                        if _find_col(row, "PURCHASE AMOUNT") is not None
                        else _find_col(row, "MARKET PURCHASE"),
                        "scheme": _find_col(row, "AMC NAME"),
                    }
                    mode = "purchase"
                    continue

                if mode == "summary":
                    code = _cell(row, summary_cols.get("code"))
                    desc = _cell(row, summary_cols.get("desc"))
                    if not code and not desc:
                        continue
                    _flush_portal_item(item, doc)
                    item = _PortalItem(
                        category=_portal_category(code, desc),
                        code=code,
                        desc=desc,
                        source=_cell(row, summary_cols.get("source")),
                        amount=to_paise(_cell(row, summary_cols.get("amount"))),
                    )
                    found = True
                elif mode in ("interest", "sale", "purchase") and item is not None:
                    if _portal_detail_entry(item, mode, detail_cols, row, doc):
                        item.had_details = True

    _flush_portal_item(item, doc)
    return found


_CATEGORY_LINE_RE = re.compile(
    r"Information\s+Category[:\s]+(.+)", re.IGNORECASE
)


def parse_ais_pdf(pdf_bytes: bytes, *, password: str | None = None) -> AISDocument:
    """Parse an AIS PDF and return a structured AISDocument.

    Uses a state-machine over text pages:
    1. Detect "Information Category: XXX" lines to track the active category.
    2. Dispatch tables to the active category handler.

    If the PDF appears to be image-based (no text extracted), emits a warning.

    Raises
    ------
    PdfPasswordError
        When the PDF is encrypted and *password* is missing or wrong. AIS
        downloads are protected by default (PAN in lowercase + DOB ddmmyyyy).
    """
    doc = AISDocument(source="pdf")

    pages_text = extract_text_pages(pdf_bytes, password=password)
    pages_tables = extract_tables_pages(pdf_bytes, password=password)

    if not pages_text:
        doc.warnings.append(
            ParserWarning(
                code="pdf_open_failed",
                message="Could not open the AIS PDF.",
            )
        )
        return doc

    # Check if ANY text was extracted
    all_text = "\n".join(pages_text)
    if not all_text.strip():
        doc.warnings.append(
            ParserWarning(
                code="scanned_pdf_unsupported",
                message="AIS PDF appears to be image-based; text extraction failed",
            )
        )
        return doc

    # Extract PAN and AY from the full text
    doc.pan = parse_pan(all_text)
    ay_raw = parse_assessment_year(all_text)
    doc.assessment_year = ay_raw

    # Extract name if present (heuristic)
    m = re.search(r"Name[:\s]+([A-Z][A-Za-z\s]{2,50})", all_text)
    if m:
        doc.name = m.group(1).strip()

    any_tables_found = any(
        table for page_tables in pages_tables for table in page_tables
    )

    # Real e-filing portal downloads: INFORMATION CODE summary rows with
    # detail tables. When that layout is present it is authoritative —
    # the legacy "Information Category:" pass below would find nothing.
    if _parse_portal_tables(pages_tables, doc):
        _compute_totals(doc)
        return doc

    # State machine: track the active category as we iterate pages
    current_category: str | None = None

    for page_idx, (page_text, page_tables) in enumerate(
        zip(pages_text, pages_tables, strict=False)
    ):
        for line in page_text.splitlines():
            m = _CATEGORY_LINE_RE.search(line)
            if m:
                current_category = m.group(1).strip()

        for table in page_tables:
            if not table:
                continue
            any_tables_found = True
            if current_category is None:
                continue

            handler = _CATEGORY_DISPATCH.get(current_category)
            if handler is None:
                doc.warnings.append(
                    ParserWarning(
                        code="unknown_category",
                        message=f"Unrecognized AIS category: {current_category}",
                        location=f"page {page_idx + 1}",
                    )
                )
                continue

            # Convert table rows into transaction dicts and dispatch
            if not table or len(table) < 2:
                continue
            headers = [normalize_cell(c) for c in table[0]]
            for row in table[1:]:
                txn: dict[str, str] = {}
                for col_idx, cell in enumerate(row):
                    if col_idx < len(headers):
                        txn[headers[col_idx]] = normalize_cell(cell)
                try:
                    handler(txn, doc)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "AIS PDF handler error for category %s page %d: %s",
                        current_category,
                        page_idx + 1,
                        exc,
                    )

    if not any_tables_found:
        doc.warnings.append(
            ParserWarning(
                code="scanned_pdf_unsupported",
                message="AIS PDF appears to be image-based; text extraction failed",
            )
        )

    _compute_totals(doc)
    return doc
