"""Form 16 PDF parser — Part A + Part B.

Entry point:
    parse_form16(pdf_bytes: bytes, *, password: str | None = None) -> Form16Document

The parser uses pdfplumber to extract text and tables, then applies
regex-anchored extraction for structured fields.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

from kara_api.parsers._text_utils import (
    extract_assessment_year,
    extract_pan,
    extract_tan,
    to_int,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class QuarterlyTDS(BaseModel):
    quarter: Literal["Q1", "Q2", "Q3", "Q4"]
    receipt_number: str | None = None
    amount_paid_credited: int = 0
    tax_deducted: int = 0
    tax_deposited: int = 0


class Form16PartA(BaseModel):
    employer_name: str
    employer_address: str | None = None
    employer_tan: str
    employer_pan: str | None = None
    employee_name: str
    employee_pan: str
    assessment_year: str
    period_from: date | None = None
    period_to: date | None = None
    quarterly_tds: list[QuarterlyTDS] = []
    total_tds_deposited: int = 0


class Sec10Exemptions(BaseModel):
    hra: int = 0
    lta: int = 0
    gratuity: int = 0
    leave_encashment: int = 0
    other: int = 0
    total: int = 0


class ChapterVIADeductions(BaseModel):
    sec_80c: int = 0
    sec_80ccc: int = 0
    sec_80ccd_1: int = 0
    sec_80ccd_1b: int = 0
    sec_80ccd_2: int = 0
    sec_80d: int = 0
    sec_80e: int = 0
    sec_80g: int = 0
    sec_80tta: int = 0
    sec_80ttb: int = 0
    other: int = 0
    total: int = 0


class Form16PartB(BaseModel):
    gross_salary: int = 0
    salary_section_17_1: int = 0
    perquisites_section_17_2: int = 0
    profits_in_lieu_section_17_3: int = 0
    sec10_exemptions: Sec10Exemptions = Sec10Exemptions()
    standard_deduction: int = 0
    professional_tax: int = 0
    entertainment_allowance: int = 0
    income_under_salaries: int = 0
    income_other_sources: int = 0
    gross_total_income: int = 0
    chapter_via: ChapterVIADeductions = ChapterVIADeductions()
    taxable_income: int = 0
    tax_on_total_income: int = 0
    rebate_87a: int = 0
    surcharge: int = 0
    health_education_cess: int = 0
    tax_payable: int = 0
    relief_section_89: int = 0
    net_tax_payable: int = 0


class Form16Document(BaseModel):
    part_a: Form16PartA
    part_b: Form16PartB | None = None
    raw_text_excerpt: str | None = None
    parser_version: str = "1.0"
    warnings: list[str] = []


class Form16ParseError(ValueError):
    """Raised when the PDF is unrecognisable as a Form 16."""


# ---------------------------------------------------------------------------
# Label map: normalised label text  ->  dotted field path on Form16PartB
#
# IMPORTANT: entries are ordered longest-first so that more specific patterns
# always win over shorter ones that could be a substring match.  For example
# "net tax payable" must appear before "tax payable", and
# "tax on total income" before "total income".
# ---------------------------------------------------------------------------

LABEL_MAP: dict[str, str] = {
    # Full-length labels first (longest → shortest within each group)
    "salary as per provisions contained in section 17(1)": "salary_section_17_1",
    "value of perquisites under section 17(2)": "perquisites_section_17_2",
    "profits in lieu of salary under section 17(3)": "profits_in_lieu_section_17_3",
    "aggregate of deductible amount under chapter vi-a": "chapter_via.total",
    "income chargeable under the head salaries": "income_under_salaries",
    "standard deduction under section 16(ia)": "standard_deduction",
    "deduction in respect of life insurance": "chapter_via.sec_80c",
    "deduction in respect of health insurance": "chapter_via.sec_80d",
    "deduction under section 80ccd(1b)": "chapter_via.sec_80ccd_1b",
    "deduction under section 80ccd(2)": "chapter_via.sec_80ccd_2",
    "income from other sources": "income_other_sources",
    "rebate under section 87a": "rebate_87a",
    "leave travel concession": "sec10_exemptions.lta",
    "relief under section 89": "relief_section_89",
    "health and education cess": "health_education_cess",
    "entertainment allowance": "entertainment_allowance",
    "house rent allowance": "sec10_exemptions.hra",
    "tax on total income": "tax_on_total_income",  # MUST come before "total income"
    "gross total income": "gross_total_income",      # MUST come before "gross salary"
    "net tax payable": "net_tax_payable",            # MUST come before "tax payable"
    "leave encashment": "sec10_exemptions.leave_encashment",
    "standard deduction": "standard_deduction",
    "professional tax": "professional_tax",
    # Matched after "tax on total income" and "gross total income":
    "total income": "taxable_income",
    "gross salary": "gross_salary",
    "tax payable": "tax_payable",                    # after "net tax payable"
    "surcharge": "surcharge",
    "gratuity": "sec10_exemptions.gratuity",
    "80ccd(1b)": "chapter_via.sec_80ccd_1b",
    "80ccd(2)": "chapter_via.sec_80ccd_2",
    "80ttb": "chapter_via.sec_80ttb",
    "80tta": "chapter_via.sec_80tta",
    "80c": "chapter_via.sec_80c",
    "80d": "chapter_via.sec_80d",
    "80e": "chapter_via.sec_80e",
    "80g": "chapter_via.sec_80g",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PART_A_RE = re.compile(r"PART\s*[-–]?\s*A\b", re.IGNORECASE)
_PART_B_RE = re.compile(r"PART\s*[-–]?\s*B\b|Annexure\b", re.IGNORECASE)

# Patterns for date extraction: DD/MM/YYYY or DD-MM-YYYY
_DATE_RE = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b")


def _parse_date(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _rightmost_number_on_line(line: str) -> str:
    """Return the last token on *line* that looks like a number."""
    # Match Indian formatted numbers possibly with decimal, optionally in parens
    tokens = re.findall(r"\([\d,]+(?:\.\d+)?\)|[\d,]+(?:\.\d+)?", line)
    return tokens[-1] if tokens else ""


def _set_nested(obj: Any, path: str, value: int) -> None:
    """Set *value* on *obj* following a dotted *path* (max 2 levels)."""
    parts = path.split(".", 1)
    if len(parts) == 1:
        setattr(obj, parts[0], value)
    else:
        child = getattr(obj, parts[0])
        setattr(child, parts[1], value)


# ---------------------------------------------------------------------------
# Part A extraction
# ---------------------------------------------------------------------------


def _extract_part_a(pages: list[Any], warnings: list[str]) -> Form16PartA:
    """Extract structured Part A data from a list of pdfplumber page objects."""
    full_text = "\n".join(p.extract_text() or "" for p in pages)

    # --- PAN / TAN ---
    employer_tan = extract_tan(full_text) or "UNKNOWN0000X"
    employee_pan = extract_pan(full_text) or "UNKNOWN0000X"

    # Employer PAN is a second PAN — try to grab two and pick the right one
    all_pans = re.findall(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", full_text)
    # Heuristic: employer PAN type is typically 'P' (4th char) for companies
    # Employee PAN type is 'P' for individuals.  We just take both if distinct.
    employer_pan: str | None = None
    if len(all_pans) >= 2:
        for pan in all_pans:
            if pan != employee_pan:
                employer_pan = pan
                break

    # --- Assessment year ---
    assessment_year = extract_assessment_year(full_text) or "2025-26"

    # --- Employer name: look for "Name of Employer" label ---
    employer_name = "Unknown Employer"
    m = re.search(
        r"(?:Name\s+of\s+(?:the\s+)?[Ee]mployer|Employer['\s]*[Nn]ame)[:\s]+([^\n]+)",
        full_text,
    )
    if m:
        employer_name = m.group(1).strip()

    # --- Employee name ---
    employee_name = "Unknown Employee"
    m = re.search(
        r"(?:Name\s+of\s+(?:the\s+)?[Ee]mployee|Employee['\s]*[Nn]ame)[:\s]+([^\n]+)",
        full_text,
    )
    if m:
        employee_name = m.group(1).strip()

    # --- Employer address ---
    employer_address: str | None = None
    m = re.search(
        r"(?:Address\s+of\s+(?:the\s+)?[Ee]mployer|Employer['\s]*[Aa]ddress)[:\s]+([^\n]+(?:\n[^\n]+){0,2})",
        full_text,
    )
    if m:
        employer_address = m.group(1).strip()

    # --- Period from / to ---
    period_from: date | None = None
    period_to: date | None = None
    m = re.search(
        r"[Pp]eriod\s+(?:of\s+)?[Ee]mployment[:\s]+(\S+)\s+[Tt]o\s+(\S+)",
        full_text,
    )
    if m:
        period_from = _parse_date(m.group(1))
        period_to = _parse_date(m.group(2))

    # --- Quarterly TDS table ---
    quarterly_tds: list[QuarterlyTDS] = []
    total_tds_deposited = 0

    for page in pages:
        tables = page.extract_tables() or []
        for table in tables:
            if not table:
                continue
            # Detect by header row or first data cell
            header = [str(c).lower() if c else "" for c in table[0]]
            is_tds_table = any("quarter" in h for h in header) or (
                table[0] and str(table[0][0]).strip().upper() in ("Q1", "Q2", "Q3", "Q4")
            )
            if not is_tds_table and len(table) > 1:
                # Check first data cell
                first_cell = str(table[1][0]).strip().upper() if table[1][0] else ""
                is_tds_table = first_cell in ("Q1", "Q2", "Q3", "Q4")

            if not is_tds_table:
                continue

            # Determine column indices
            # Expected: Quarter | Receipt No | Amount paid/credited | Tax Deducted | Tax Deposited
            col_quarter = 0
            col_receipt = 1
            col_amount = 2
            col_deducted = 3
            col_deposited = 4

            # Try to map from header if present
            if "quarter" in header:
                for i, h in enumerate(header):
                    if "quarter" in h:
                        col_quarter = i
                    elif "receipt" in h:
                        col_receipt = i
                    elif "amount" in h or "credited" in h or "paid" in h:
                        col_amount = i
                    elif "deducted" in h:
                        col_deducted = i
                    elif "deposited" in h:
                        col_deposited = i

            for row in table[1:]:  # skip header
                if not row or len(row) < 2:
                    continue
                q_cell = str(row[col_quarter]).strip().upper() if row[col_quarter] else ""
                if q_cell not in ("Q1", "Q2", "Q3", "Q4"):
                    continue

                def _cell(idx: int) -> str:
                    if idx < len(row) and row[idx]:
                        return str(row[idx]).strip()
                    return "0"

                receipt = _cell(col_receipt) if col_receipt < len(row) else None
                amount = to_int(_cell(col_amount))
                deducted = to_int(_cell(col_deducted))
                deposited = to_int(_cell(col_deposited))

                quarterly_tds.append(
                    QuarterlyTDS(
                        quarter=q_cell,  # type: ignore[arg-type]
                        receipt_number=receipt if receipt and receipt != "0" else None,
                        amount_paid_credited=amount,
                        tax_deducted=deducted,
                        tax_deposited=deposited,
                    )
                )
                total_tds_deposited += deposited

    # If table parsing found nothing, warn but continue
    if not quarterly_tds:
        warnings.append("Could not find quarterly TDS table in Part A.")

    return Form16PartA(
        employer_name=employer_name,
        employer_address=employer_address,
        employer_tan=employer_tan,
        employer_pan=employer_pan,
        employee_name=employee_name,
        employee_pan=employee_pan,
        assessment_year=assessment_year,
        period_from=period_from,
        period_to=period_to,
        quarterly_tds=quarterly_tds,
        total_tds_deposited=total_tds_deposited,
    )


# ---------------------------------------------------------------------------
# Part B extraction
# ---------------------------------------------------------------------------


def _extract_part_b(pages: list[Any], warnings: list[str]) -> Form16PartB:
    """Extract structured Part B data from a list of pdfplumber page objects."""
    part_b = Form16PartB()

    for page in pages:
        # --- Try table-based extraction first ---
        tables = page.extract_tables() or []
        for table in tables:
            for row in table:
                if not row or len(row) < 2:
                    continue
                label_raw = str(row[0]).strip() if row[0] else ""
                value_raw = str(row[-1]).strip() if row[-1] else ""
                if not label_raw or not value_raw:
                    continue
                label_norm = re.sub(r"\s+", " ", label_raw.lower())
                _apply_label_value(part_b, label_norm, value_raw, warnings)

        # --- Fall back to line-by-line text extraction ---
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Split label (left side) from value (rightmost number)
            value_str = _rightmost_number_on_line(line)
            if not value_str:
                continue
            # Remove the value from the end to get the label portion
            label_part = line[: line.rfind(value_str)].strip()
            if not label_part:
                continue
            label_norm = re.sub(r"\s+", " ", label_part.lower())
            # Only apply if we get a match (avoid overwriting with garbage)
            _apply_label_value(part_b, label_norm, value_str, warnings, strict=True)

    return part_b


def _apply_label_value(
    part_b: Form16PartB,
    label_norm: str,
    value_raw: str,
    warnings: list[str],
    strict: bool = False,
) -> bool:
    """Match *label_norm* against LABEL_MAP and set the corresponding field.

    Returns True if a match was found.  When *strict* is True, only exact
    substring matches are used (avoids false positives from free text).
    """
    for pattern, field_path in LABEL_MAP.items():
        if strict:
            # Require the pattern to appear as a substantial portion of the label
            if pattern not in label_norm:
                continue
            # Avoid very short patterns matching unrelated lines
            if len(pattern) < 6 and pattern not in label_norm.split():
                continue
        else:
            if pattern not in label_norm:
                continue

        amount = to_int(value_raw)
        try:
            _set_nested(part_b, field_path, amount)
        except AttributeError as exc:
            warnings.append(f"Could not set field '{field_path}': {exc}")
        return True
    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_form16(pdf_bytes: bytes, *, password: str | None = None) -> Form16Document:
    """Parse a Form 16 PDF and return a structured :class:`Form16Document`.

    Parameters
    ----------
    pdf_bytes:
        Raw PDF bytes.  May be encrypted (provide *password* in that case).
    password:
        Optional PDF password for encrypted documents.

    Raises
    ------
    Form16ParseError
        If the document is not a valid PDF, is encrypted with the wrong
        password, or does not contain a recognisable Form 16 Part A section.
    """
    import pdfplumber

    # --- Open PDF ---
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes), password=password)
    except Exception as exc:
        exc_name = type(exc).__name__.lower()
        msg = str(exc).lower()
        if "password" in exc_name or "password" in msg or "encrypt" in msg or "crypt" in msg:
            raise Form16ParseError("PDF is encrypted — please provide the password.") from exc
        raise Form16ParseError(f"Cannot open PDF: {exc}") from exc

    warnings: list[str] = []
    part_a_pages: list[Any] = []
    part_b_pages: list[Any] = []
    all_text_lines: list[str] = []

    with pdf:
        if not pdf.pages:
            raise Form16ParseError("Not a Form 16: PDF has no pages.")

        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text_lines.append(text[:500])  # keep first 500 chars per page for excerpt

            if _PART_A_RE.search(text):
                part_a_pages.append(page)
            if _PART_B_RE.search(text):
                part_b_pages.append(page)
            # A page can belong to both buckets if it contains both markers

        if not part_a_pages:
            raise Form16ParseError(
                "Not a Form 16: could not find a PART A section in the document."
            )

        raw_excerpt = "\n---\n".join(all_text_lines[:4])[:2000]

        part_a = _extract_part_a(part_a_pages, warnings)
        part_b: Form16PartB | None = None
        if part_b_pages:
            part_b = _extract_part_b(part_b_pages, warnings)
        else:
            warnings.append("No PART B / Annexure section found — part_b is None.")

    return Form16Document(
        part_a=part_a,
        part_b=part_b,
        raw_text_excerpt=raw_excerpt,
        warnings=warnings,
    )
