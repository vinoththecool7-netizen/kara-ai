"""Reportlab-based and dict-based AIS fixtures.

build_ais_json() — returns a dict matching the AIS_Data JSON structure.
build_ais_pdf()  — returns a reportlab PDF bytes that the AIS parser can read.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_STYLES = getSampleStyleSheet()
_NORMAL = _STYLES["Normal"]
_H2 = _STYLES["Heading2"]


# ---------------------------------------------------------------------------
# Shared PDF helpers
# ---------------------------------------------------------------------------


def _build_pdf(story: list, *, password: str | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="AIS", encrypt=password)
    doc.build(story)
    return buf.getvalue()


def _heading(text: str) -> Paragraph:
    return Paragraph(f"<b>{text}</b>", _H2)


def _para(text: str) -> Paragraph:
    return Paragraph(text, _NORMAL)


def _spacer() -> Spacer:
    return Spacer(1, 0.3 * cm)


def _simple_table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Build a bordered table from a list-of-lists of strings."""
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    return tbl


# ---------------------------------------------------------------------------
# JSON factory
# ---------------------------------------------------------------------------


def build_ais_json(
    *,
    pan: str = "ABCDE1234F",
    ay: str = "2025-26",
) -> dict:
    """Build a minimal AIS JSON dict.

    Populated categories:
    - "192" (salary) — one entry
    - "194A" (interest savings) — one entry
    - "SFT-011" (security sale) — one entry
    - "SFT-999" (unknown/unsupported) — one entry  ← to test mismatch tolerance
    """
    return {
        "PAN": pan,
        "Assessment_Year": ay,
        "Name": "Rajesh Kumar",
        "AIS_Data": [
            {
                "Information_Category": "192",
                "Category_Description": "TDS on Salary",
                "Transaction_Data": [
                    {
                        "Deductor_Name": "Acme Software Pvt Ltd",
                        "TAN": "PUNE12345F",
                        "Amount_Paid": "1200000",
                        "TDS_Amount": "60000",
                    }
                ],
            },
            {
                "Information_Category": "194A",
                "Category_Description": "Interest other than interest on securities",
                "Transaction_Data": [
                    {
                        "Payer_Name": "State Bank of India",
                        "TAN": "MUMB11111B",
                        "Interest_Amount": "45000",
                        "TDS_Amount": "4500",
                        "Account_Type": "Savings",
                    }
                ],
            },
            {
                "Information_Category": "SFT-011",
                "Category_Description": "Sale of securities and units of mutual fund",
                "Transaction_Data": [
                    {
                        "ISIN": "INE009A01021",
                        "Scrip_Name": "Infosys Ltd",
                        "Quantity": "100",
                        "Sale_Value": "1500000",
                        "Transaction_Date": "15-Mar-2025",
                        "Broker_Name": "Zerodha",
                    }
                ],
            },
            {
                # Unknown category — must emit warning and not crash
                "Information_Category": "SFT-999",
                "Category_Description": "Unknown / future category",
                "Transaction_Data": [
                    {"Amount": "999", "Name": "Mystery Entry"}
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# PDF factory
# ---------------------------------------------------------------------------


def build_ais_pdf(
    *,
    pan: str = "ABCDE1234F",
    ay: str = "2025-26",
    password: str | None = None,
) -> bytes:
    """Build a reportlab AIS PDF with the same data as build_ais_json().

    Each category is preceded by an "Information Category: <code>" heading
    followed by a simple data table so the AIS PDF parser can extract them.
    """
    story: list = [
        _heading("Annual Information Statement (AIS)"),
        _para(f"PAN: {pan}"),
        _para(f"Assessment Year: {ay}"),
        _para("Name: Rajesh Kumar"),
        _spacer(),
        # --- Salary category ---
        _para("Information Category: 192"),
        _spacer(),
        _simple_table(
            [
                ["Deductor Name", "TAN", "Amount Paid", "TDS Amount"],
                ["Acme Software Pvt Ltd", "PUNE12345F", "12,00,000", "60,000"],
            ],
            col_widths=[6 * cm, 4 * cm, 4 * cm, 4 * cm],
        ),
        _spacer(),
        # --- Interest category ---
        _para("Information Category: 194A"),
        _spacer(),
        _simple_table(
            [
                ["Payer Name", "TAN", "Interest Amount", "TDS Amount"],
                ["State Bank of India", "MUMB11111B", "45,000", "4,500"],
            ],
            col_widths=[6 * cm, 4 * cm, 4 * cm, 4 * cm],
        ),
        _spacer(),
        # --- Securities sale ---
        _para("Information Category: SFT-011"),
        _spacer(),
        _simple_table(
            [
                ["ISIN", "Scrip Name", "Quantity", "Sale Value", "Date"],
                ["INE009A01021", "Infosys Ltd", "100", "15,00,000", "15-Mar-2025"],
            ],
            col_widths=[4 * cm, 4 * cm, 2 * cm, 4 * cm, 4 * cm],
        ),
        _spacer(),
    ]

    return _build_pdf(story, password=password)
