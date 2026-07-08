"""Form 26AS (Tax Credit Statement) parser.

Entry point:
    parse_form_26as(pdf_bytes: bytes) -> Form26ASDocument

Form 26AS is a PDF-only document from TRACES.  The parser uses pdfplumber to
extract text and tables, then buckets each table into the detected PART.

Recognised parts:
    PART A   — TDS on salary (section 192)
    PART A1  — TDS on other income
    PART B   — TCS
    PART C   — Advance tax / self-assessment tax (minor head 100 / 300)
    PART D   — Refunds
    PART E   — AIR / SFT (optional)
    PART F   — TDS on sale of immovable property (optional)
    PART G   — TDS defaults (optional)

Only Parts A, A1, B, C, D are fully parsed; others are silently ignored.

pdfplumber pain points handled:
    - Cell merging: forward-fill None cells in first column from the previous row
      when later columns are populated (deductor name spans two rows).
    - Header repetition: skip rows where the first cell equals "Sr. No." or the
      entire row is identical to the previous row.
"""
from __future__ import annotations

import logging
import re
from datetime import date

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
    to_paise,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TDSSalaryEntry(BaseModel):
    deductor_tan: str = ""
    deductor_name: str = ""
    section: str = "192"
    amount_paid_credited: int = 0  # paise
    tax_deducted: int = 0
    tax_deposited: int = 0
    transaction_date: date | None = None


class TDSOtherEntry(BaseModel):
    deductor_tan: str = ""
    deductor_name: str = ""
    section: str = ""
    amount_paid_credited: int = 0
    tax_deducted: int = 0
    tax_deposited: int = 0
    transaction_date: date | None = None


class TCSEntry(BaseModel):
    collector_tan: str = ""
    collector_name: str = ""
    section: str = ""
    amount_paid_debited: int = 0
    tcs_collected: int = 0
    tcs_deposited: int = 0


class AdvanceTaxEntry(BaseModel):
    bsr_code: str = ""
    challan_serial: str = ""
    deposit_date: date | None = None
    amount: int = 0  # paise
    minor_head: str = "100"


class SelfAssessmentEntry(BaseModel):
    bsr_code: str = ""
    challan_serial: str = ""
    deposit_date: date | None = None
    amount: int = 0
    minor_head: str = "300"


class RefundEntry26AS(BaseModel):
    assessment_year: str = ""
    mode: str = ""
    refund_amount: int = 0
    interest: int = 0
    date_of_payment: date | None = None


class Form26ASTotals(BaseModel):
    total_tds_salary: int = 0
    total_tds_other: int = 0
    total_advance_tax: int = 0
    total_self_assessment: int = 0
    total_refunds: int = 0


class Form26ASDocument(BaseParsedDocument):
    name: str = ""
    address: str = ""
    tds_on_salary: list[TDSSalaryEntry] = []
    tds_on_other_income: list[TDSOtherEntry] = []
    tds_no_pan: list[TDSOtherEntry] = []
    tcs: list[TCSEntry] = []
    advance_tax_paid: list[AdvanceTaxEntry] = []
    self_assessment_tax: list[SelfAssessmentEntry] = []
    refunds: list[RefundEntry26AS] = []
    totals: Form26ASTotals = Form26ASTotals()


# ---------------------------------------------------------------------------
# Part detection regex
# ---------------------------------------------------------------------------

_PART_RE = re.compile(
    r"\bPART\s+(A1|A2|A|B|C|D|E|F|G)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Table cell utilities
# ---------------------------------------------------------------------------


def _forward_fill_first_col(
    table: list[list[str | None]],
) -> list[list[str]]:
    """Return a copy of *table* with None/empty first-column cells filled from the previous row.

    Also normalises all cells via normalize_cell.
    """
    result: list[list[str]] = []
    last_first_col = ""
    for row in table:
        norm_row = [normalize_cell(c) for c in row]
        if norm_row:
            if not norm_row[0] and last_first_col:
                norm_row[0] = last_first_col
            else:
                last_first_col = norm_row[0]
        result.append(norm_row)
    return result


def _is_header_row(row: list[str]) -> bool:
    """Return True if *row* looks like a repeated column-header row."""
    first = row[0].lower() if row else ""
    return first in ("sr. no.", "sr no", "sr.", "s.no", "sl.no", "sl no", "no.")


def _dedupe_rows(table: list[list[str]]) -> list[list[str]]:
    """Remove exact duplicate rows and header-repetition rows."""
    seen: set[tuple[str, ...]] = set()
    result: list[list[str]] = []
    for row in table:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _safe_get(row: list[str], idx: int) -> str:
    return row[idx] if idx < len(row) else ""


# ---------------------------------------------------------------------------
# Part-specific parsers
# ---------------------------------------------------------------------------


def _parse_part_a(
    tables: list[list[list[str | None]]],
    doc: Form26ASDocument,
) -> None:
    """Parse PART A — TDS deducted on salary (section 192)."""
    for raw_table in tables:
        if not raw_table or len(raw_table) < 2:
            continue
        table = _forward_fill_first_col(raw_table)
        table = _dedupe_rows(table)

        # Detect header row to find column indices
        # Expected columns: Sr No, TAN, Deductor Name, Amount Paid, Tax Deducted, Tax Deposited
        header = table[0]
        col_tan = _find_col(header, ["tan", "deductor tan"])
        col_name = _find_col(header, ["name", "deductor name"])
        col_amount = _find_col(header, ["amount paid", "amount credited", "amount"])
        col_deducted = _find_col(header, ["tax deducted"])
        col_deposited = _find_col(header, ["tax deposited", "deposited"])
        col_date = _find_col(header, ["date", "transaction date"])

        for row in table[1:]:
            if not row or _is_header_row(row):
                continue
            # Skip rows that are all-empty
            if not any(c.strip() for c in row):
                continue

            tan_val = _safe_get(row, col_tan) if col_tan is not None else ""
            name_val = _safe_get(row, col_name) if col_name is not None else ""
            amount_val = _safe_get(row, col_amount) if col_amount is not None else "0"
            deducted_val = _safe_get(row, col_deducted) if col_deducted is not None else "0"
            deposited_val = _safe_get(row, col_deposited) if col_deposited is not None else "0"
            date_val = _safe_get(row, col_date) if col_date is not None else ""

            doc.tds_on_salary.append(
                TDSSalaryEntry(
                    deductor_tan=tan_val,
                    deductor_name=name_val,
                    section="192",
                    amount_paid_credited=to_paise(amount_val),
                    tax_deducted=to_paise(deducted_val),
                    tax_deposited=to_paise(deposited_val),
                    transaction_date=parse_date_flexible(date_val),
                )
            )


def _parse_part_a1(
    tables: list[list[list[str | None]]],
    doc: Form26ASDocument,
) -> None:
    """Parse PART A1 — TDS on other income."""
    for raw_table in tables:
        if not raw_table or len(raw_table) < 2:
            continue
        table = _forward_fill_first_col(raw_table)
        table = _dedupe_rows(table)

        header = table[0]
        col_tan = _find_col(header, ["tan", "deductor tan"])
        col_name = _find_col(header, ["name", "deductor name"])
        col_section = _find_col(header, ["section"])
        col_amount = _find_col(header, ["amount paid", "amount credited", "amount"])
        col_deducted = _find_col(header, ["tax deducted"])
        col_deposited = _find_col(header, ["tax deposited", "deposited"])

        for row in table[1:]:
            if not row or _is_header_row(row):
                continue
            if not any(c.strip() for c in row):
                continue

            doc.tds_on_other_income.append(
                TDSOtherEntry(
                    deductor_tan=_safe_get(row, col_tan) if col_tan is not None else "",
                    deductor_name=_safe_get(row, col_name) if col_name is not None else "",
                    section=_safe_get(row, col_section) if col_section is not None else "",
                    amount_paid_credited=to_paise(
                        _safe_get(row, col_amount) if col_amount is not None else "0"
                    ),
                    tax_deducted=to_paise(
                        _safe_get(row, col_deducted) if col_deducted is not None else "0"
                    ),
                    tax_deposited=to_paise(
                        _safe_get(row, col_deposited) if col_deposited is not None else "0"
                    ),
                )
            )


def _parse_part_b(
    tables: list[list[list[str | None]]],
    doc: Form26ASDocument,
) -> None:
    """Parse PART B — TCS."""
    for raw_table in tables:
        if not raw_table or len(raw_table) < 2:
            continue
        table = _forward_fill_first_col(raw_table)
        table = _dedupe_rows(table)

        header = table[0]
        col_tan = _find_col(header, ["tan", "collector tan"])
        col_name = _find_col(header, ["name", "collector name"])
        col_section = _find_col(header, ["section"])
        col_amount = _find_col(header, ["amount", "amount paid", "amount debited"])
        col_collected = _find_col(header, ["tcs collected", "tax collected"])
        col_deposited = _find_col(header, ["tcs deposited", "tax deposited", "deposited"])

        for row in table[1:]:
            if not row or _is_header_row(row):
                continue
            if not any(c.strip() for c in row):
                continue

            doc.tcs.append(
                TCSEntry(
                    collector_tan=_safe_get(row, col_tan) if col_tan is not None else "",
                    collector_name=_safe_get(row, col_name) if col_name is not None else "",
                    section=_safe_get(row, col_section) if col_section is not None else "",
                    amount_paid_debited=to_paise(
                        _safe_get(row, col_amount) if col_amount is not None else "0"
                    ),
                    tcs_collected=to_paise(
                        _safe_get(row, col_collected) if col_collected is not None else "0"
                    ),
                    tcs_deposited=to_paise(
                        _safe_get(row, col_deposited) if col_deposited is not None else "0"
                    ),
                )
            )


def _parse_part_c(
    tables: list[list[list[str | None]]],
    doc: Form26ASDocument,
) -> None:
    """Parse PART C — Advance tax / self-assessment tax.

    Minor head 100 = advance tax; 300 = self-assessment tax.
    """
    for raw_table in tables:
        if not raw_table or len(raw_table) < 2:
            continue
        table = _forward_fill_first_col(raw_table)
        table = _dedupe_rows(table)

        header = table[0]
        col_bsr = _find_col(header, ["bsr code", "bsr"])
        col_challan = _find_col(header, ["challan serial", "challan no", "serial"])
        col_date = _find_col(header, ["deposit date", "date of deposit", "date"])
        col_amount = _find_col(header, ["amount", "tax deposited"])
        col_minor = _find_col(header, ["minor head", "type", "nature"])

        for row in table[1:]:
            if not row or _is_header_row(row):
                continue
            if not any(c.strip() for c in row):
                continue

            bsr = _safe_get(row, col_bsr) if col_bsr is not None else ""
            challan = _safe_get(row, col_challan) if col_challan is not None else ""
            date_str = _safe_get(row, col_date) if col_date is not None else ""
            amount_str = _safe_get(row, col_amount) if col_amount is not None else "0"
            minor_raw = (_safe_get(row, col_minor) if col_minor is not None else "").lower()

            dep_date = parse_date_flexible(date_str)
            amount_paise = to_paise(amount_str)

            # Detect minor head: "300" or "self assessment" → self-assessment
            if "300" in minor_raw or "self" in minor_raw:
                doc.self_assessment_tax.append(
                    SelfAssessmentEntry(
                        bsr_code=bsr,
                        challan_serial=challan,
                        deposit_date=dep_date,
                        amount=amount_paise,
                        minor_head="300",
                    )
                )
            else:
                # Default to advance tax (minor head 100)
                doc.advance_tax_paid.append(
                    AdvanceTaxEntry(
                        bsr_code=bsr,
                        challan_serial=challan,
                        deposit_date=dep_date,
                        amount=amount_paise,
                        minor_head="100",
                    )
                )


def _parse_part_d(
    tables: list[list[list[str | None]]],
    doc: Form26ASDocument,
) -> None:
    """Parse PART D — Refunds."""
    for raw_table in tables:
        if not raw_table or len(raw_table) < 2:
            continue
        table = _forward_fill_first_col(raw_table)
        table = _dedupe_rows(table)

        header = table[0]
        col_ay = _find_col(header, ["assessment year", "ay"])
        col_mode = _find_col(header, ["mode", "payment mode", "refund mode"])
        col_amount = _find_col(header, ["amount", "refund amount"])
        col_interest = _find_col(header, ["interest", "interest amount"])
        col_date = _find_col(header, ["date", "date of payment", "payment date"])

        for row in table[1:]:
            if not row or _is_header_row(row):
                continue
            if not any(c.strip() for c in row):
                continue

            doc.refunds.append(
                RefundEntry26AS(
                    assessment_year=_safe_get(row, col_ay) if col_ay is not None else "",
                    mode=_safe_get(row, col_mode) if col_mode is not None else "",
                    refund_amount=to_paise(
                        _safe_get(row, col_amount) if col_amount is not None else "0"
                    ),
                    interest=to_paise(
                        _safe_get(row, col_interest) if col_interest is not None else "0"
                    ),
                    date_of_payment=parse_date_flexible(
                        _safe_get(row, col_date) if col_date is not None else ""
                    ),
                )
            )


def _find_col(header: list[str], keywords: list[str]) -> int | None:
    """Return the index of the first header cell whose normalised text contains any keyword."""
    for i, cell in enumerate(header):
        cell_lower = cell.lower()
        if any(kw in cell_lower for kw in keywords):
            return i
    return None


# ---------------------------------------------------------------------------
# Totals computation
# ---------------------------------------------------------------------------


def _compute_totals(doc: Form26ASDocument) -> None:
    doc.totals = Form26ASTotals(
        total_tds_salary=sum(e.tax_deducted for e in doc.tds_on_salary),
        total_tds_other=sum(e.tax_deducted for e in doc.tds_on_other_income)
        + sum(e.tax_deducted for e in doc.tds_no_pan),
        total_advance_tax=sum(e.amount for e in doc.advance_tax_paid),
        total_self_assessment=sum(e.amount for e in doc.self_assessment_tax),
        total_refunds=sum(e.refund_amount for e in doc.refunds),
    )


# ---------------------------------------------------------------------------
# Part bucket: maps part label -> list of tables
# ---------------------------------------------------------------------------

_PART_HANDLERS = {
    "A": _parse_part_a,
    "A1": _parse_part_a1,
    "A2": _parse_part_a1,   # A2 = TDS where PAN not available — same shape as A1
    "B": _parse_part_b,
    "C": _parse_part_c,
    "D": _parse_part_d,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_form_26as(
    pdf_bytes: bytes, *, password: str | None = None
) -> Form26ASDocument:
    """Parse a Form 26AS PDF and return a structured Form26ASDocument.

    Parameters
    ----------
    pdf_bytes:
        Raw PDF bytes of a TRACES Form 26AS download.
    password:
        Optional PDF password. TRACES downloads are protected by default
        (date of birth as DDMMYYYY).

    Raises
    ------
    PdfPasswordError
        When the PDF is encrypted and *password* is missing or wrong.
    """
    doc = Form26ASDocument(source="pdf")

    pages_text = extract_text_pages(pdf_bytes, password=password)
    pages_tables = extract_tables_pages(pdf_bytes, password=password)

    if not pages_text:
        doc.warnings.append(
            ParserWarning(
                code="pdf_open_failed",
                message="Could not open the Form 26AS PDF.",
            )
        )
        return doc

    all_text = "\n".join(pages_text)

    # --- Extract PAN from header ---
    doc.pan = parse_pan(all_text)

    # --- Extract Assessment Year ---
    doc.assessment_year = parse_assessment_year(all_text)

    # --- Extract Name (heuristic: line after "Name:" / "Taxpayer Name:") ---
    m = re.search(r"(?:Taxpayer\s+)?Name[:\s]+([A-Z][A-Za-z\s\-]{2,60})", all_text)
    if m:
        doc.name = m.group(1).strip()

    # --- Extract Address ---
    m = re.search(r"Address[:\s]+([^\n]+(?:\n[^\n]+){0,3})", all_text)
    if m:
        doc.address = re.sub(r"\s+", " ", m.group(1)).strip()

    # --- Bucket tables per PART ---
    # Strategy: scan page text for PART markers, track the active part,
    # then assign each table on that page to that part.

    # part_tables: {"A": [table, ...], "A1": [...], ...}
    part_tables: dict[str, list[list[list[str | None]]]] = {
        p: [] for p in _PART_HANDLERS
    }
    part_tables["G"] = []   # silently accept unknown parts

    any_part_found = False
    current_part: str | None = None

    for page_idx, (page_text, page_tables_on_page) in enumerate(
        zip(pages_text, pages_tables, strict=False)
    ):
        # Check for part markers in this page's text
        for line in page_text.splitlines():
            m_part = _PART_RE.search(line)
            if m_part:
                current_part = m_part.group(1).upper()
                any_part_found = True

        # Assign all tables on this page to current_part
        for table in page_tables_on_page:
            if table and current_part in part_tables:
                part_tables[current_part].append(table)

    if not any_part_found:
        doc.warnings.append(
            ParserWarning(
                code="no_parts_detected",
                message=(
                    "No PART A/B/C/D markers found in the PDF. "
                    "The document may not be a Form 26AS."
                ),
            )
        )
        _compute_totals(doc)
        return doc

    # --- Parse each recognised part ---
    for part_label, handler in _PART_HANDLERS.items():
        tables = part_tables.get(part_label, [])
        if tables:
            try:
                handler(tables, doc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("26AS PART %s parse error: %s", part_label, exc)
                doc.warnings.append(
                    ParserWarning(
                        code=f"parse_error_part_{part_label.lower()}",
                        message=f"Error parsing PART {part_label}: {exc}",
                        location=f"PART {part_label}",
                    )
                )

    # Move A2 (no-PAN) entries into tds_no_pan
    doc.tds_no_pan = [
        TDSOtherEntry(**e.model_dump())
        for e in doc.tds_on_other_income
        if not e.deductor_tan
    ]

    _compute_totals(doc)
    return doc
