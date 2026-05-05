"""Shared helpers and base types used by all Kara document parsers.

This module is the single source of truth for:
- Shared Pydantic base models (BaseParsedDocument, ParserWarning)
- Monetary conversion (to_paise)
- PAN / TAN / AY / date normalization
- pdfplumber thin wrappers (extract_text_pages, extract_tables_pages)
- Cell normalization (normalize_cell)
"""
from __future__ import annotations

import io
import re
from datetime import date
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Warning / base document models
# ---------------------------------------------------------------------------


class ParserWarning(BaseModel):
    """A non-fatal issue encountered during parsing."""

    code: str
    message: str
    location: str | None = None


class BaseParsedDocument(BaseModel):
    """Common fields present on every parsed tax document."""

    pan: str | None = None
    assessment_year: str | None = None
    source: Literal["json", "pdf"] = "pdf"
    warnings: list[ParserWarning] = []


# ---------------------------------------------------------------------------
# Monetary conversion
# ---------------------------------------------------------------------------

_PAISE_STRIP_RE = re.compile(r"[₹Rs.\s,]", re.IGNORECASE)


def to_paise(value: str | float | int) -> int:
    """Convert a rupee amount to paise (multiply by 100).

    Handles:
    - Indian lakh formatting: "1,23,456.78"  → 12345678
    - Currency prefix:        "Rs. 1,000"    → 100000
    - Unicode symbol:         "₹5,000"       → 500000
    - Parentheses negative:   "(1,000)"      → -100000
    - Plain int/float:        1000           → 100000
    - Empty / unparseable:    ""             → 0

    Returns an integer number of paise.
    """
    if isinstance(value, int):
        return value * 100
    if isinstance(value, float):
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_DOWN) * 100)

    s = str(value).strip()
    if not s:
        return 0

    # Parentheses → negative
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    # Strip currency symbols, spaces, commas
    s = _PAISE_STRIP_RE.sub("", s)

    # Remove leading minus (handle "-1000")
    if s.startswith("-"):
        negative = not negative
        s = s[1:]

    if not s:
        return 0

    try:
        dec = Decimal(s)
        # Multiply by 100 and truncate to integer paise
        paise = int((dec * 100).to_integral_value(rounding=ROUND_DOWN))
        return -paise if negative else paise
    except InvalidOperation:
        return 0


# ---------------------------------------------------------------------------
# Identifier parsers
# ---------------------------------------------------------------------------

_PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_TAN_RE = re.compile(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b")
_AY_RE = re.compile(
    r"(?:A\.?Y\.?\s*)?(\d{4})\s*[-–]\s*(20\d{2}|\d{2})",
    re.IGNORECASE,
)


def parse_pan(s: str) -> str | None:
    """Return the first PAN found in *s*, or None."""
    m = _PAN_RE.search(s)
    return m.group(1) if m else None


def parse_tan(s: str) -> str | None:
    """Return the first TAN found in *s*, or None."""
    m = _TAN_RE.search(s)
    return m.group(1) if m else None


def parse_assessment_year(s: str) -> str | None:
    """Normalise an AY string to "YYYY-YY" short form.

    Accepts:
    - "2025-26"
    - "AY 2025-2026"
    - "A.Y. 2025-26"
    """
    m = _AY_RE.search(s)
    if not m:
        return None
    start = m.group(1)
    end_raw = m.group(2)
    end_short = end_raw[2:] if len(end_raw) == 4 else end_raw.zfill(2)
    return f"{start}-{end_short}"


# ---------------------------------------------------------------------------
# Flexible date parser
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_date_flexible(s: str) -> date | None:
    """Try several date formats and return a date, or None on failure.

    Tried in order:
    1. DD-MMM-YYYY  (e.g. 31-Mar-2025)
    2. DD/MM/YYYY
    3. DD-MM-YYYY
    4. YYYY-MM-DD
    """
    if not s:
        return None
    s = s.strip()

    # 1. DD-MMM-YYYY
    m = re.match(r"(\d{1,2})[- ]([A-Za-z]{3})[- ](\d{4})", s)
    if m:
        try:
            month = _MONTH_MAP.get(m.group(2).lower())
            if month:
                return date(int(m.group(3)), month, int(m.group(1)))
        except ValueError:
            pass

    # 2 & 3. DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # 4. YYYY-MM-DD
    m = re.match(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# pdfplumber thin wrappers
# ---------------------------------------------------------------------------


def extract_text_pages(pdf_bytes: bytes) -> list[str]:
    """Open *pdf_bytes* with pdfplumber and return per-page text strings.

    Returns an empty list if the PDF cannot be opened.
    """
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        return []


def extract_tables_pages(
    pdf_bytes: bytes,
) -> list[list[list[list[str | None]]]]:
    """Return pages → tables → rows → cells from a PDF.

    Shape: list[page] → list[table] → list[row] → list[cell]
    Each cell is str | None (as returned by pdfplumber).
    Returns an empty list on failure.
    """
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result: list[list[list[list[str | None]]]] = []
            for page in pdf.pages:
                tables = page.extract_tables() or []
                result.append(tables)
            return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Cell normalization
# ---------------------------------------------------------------------------


def normalize_cell(cell: str | None) -> str:
    """Collapse internal whitespace and strip a table cell value."""
    return re.sub(r"\s+", " ", (cell or "")).strip()
