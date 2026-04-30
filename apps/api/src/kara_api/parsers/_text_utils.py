"""Text normalization utilities for the Form 16 parser.

All helpers are pure functions with no side-effects so they are trivially
testable and can be imported from anywhere.
"""
from __future__ import annotations

import re


def to_int(value: str) -> int:
    """Convert an Indian-formatted number string to an integer.

    Handles:
    - Lakh formatting: "1,50,000"  -> 150000
    - Decimal suffix:  "1,50,000.00" -> 150000
    - Plain digits:    "150000"    -> 150000
    - Negative values: "(1,50,000)" -> -150000  (parenthesis notation)
    - Empty / junk:    ""          -> 0

    Returns 0 on any parse failure rather than raising.
    """
    if not value:
        return 0
    # Strip whitespace
    s = value.strip()
    # Handle accounting-style negative numbers wrapped in parentheses
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    # Remove currency symbols, spaces, commas
    s = re.sub(r"[₹,\s]", "", s)
    # Drop decimal part (truncate, not round — tax figures are whole rupees)
    s = re.sub(r"\.\d*$", "", s)
    # Remove any remaining non-digit characters except leading minus
    s = re.sub(r"[^\d\-]", "", s)
    if not s or s == "-":
        return 0
    try:
        result = int(s)
        return -result if negative else result
    except ValueError:
        return 0


def extract_pan(text: str) -> str | None:
    """Find the first PAN pattern in *text*.

    PAN format: 5 uppercase letters + 4 digits + 1 uppercase letter.
    Example: ABCDE1234F
    """
    match = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", text)
    return match.group(1) if match else None


def extract_tan(text: str) -> str | None:
    """Find the first TAN pattern in *text*.

    TAN format: 4 uppercase letters + 5 digits + 1 uppercase letter.
    Example: PUNE12345F
    """
    match = re.search(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b", text)
    return match.group(1) if match else None


def extract_assessment_year(text: str) -> str | None:
    """Find an assessment year string in *text*.

    Recognised patterns:
    - "2025-26"       (short form)
    - "2025-2026"     (long form)
    - "A.Y. 2025-26"  (with prefix)
    - "AY 2025-26"    (abbreviated prefix)

    Always returns the short form "YYYY-YY".
    """
    # Try long form first so we can normalise to short form
    match = re.search(
        r"(?:A\.?Y\.?\s*)?(\d{4})\s*[-–]\s*(20\d{2}|\d{2})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    start = match.group(1)
    end_raw = match.group(2)
    # Normalise end to two digits
    if len(end_raw) == 4:
        end_short = end_raw[2:]
    else:
        end_short = end_raw.zfill(2)
    return f"{start}-{end_short}"
