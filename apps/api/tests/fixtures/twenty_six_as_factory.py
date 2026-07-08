"""Reportlab-based Form 26AS PDF factory.

build_26as_pdf() — returns a reportlab PDF with PART A (salary TDS) and PART D (refund).
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_STYLES = getSampleStyleSheet()
_NORMAL = _STYLES["Normal"]
_H1 = _STYLES["Heading1"]
_H2 = _STYLES["Heading2"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pdf(story: list, *, password: str | None = None) -> bytes:
    from reportlab.lib.pagesizes import landscape
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Form 26AS",
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            encrypt=password)
    doc.build(story)
    return buf.getvalue()


def _heading1(text: str) -> Paragraph:
    return Paragraph(f"<b>{text}</b>", _H1)


def _heading2(text: str) -> Paragraph:
    return Paragraph(f"<b>{text}</b>", _H2)


def _para(text: str) -> Paragraph:
    return Paragraph(text, _NORMAL)


def _spacer() -> Spacer:
    return Spacer(1, 0.3 * cm)


def _data_table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Build a standard bordered table."""
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    return tbl


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_26as_pdf(
    *,
    pan: str = "ABCDE1234F",
    ay: str = "2025-26",
    employer_tan: str = "MUMB12345A",
    tds_salary_amount: int = 1200000,   # rupees
    tds_salary_deducted: int = 185000,  # rupees
    password: str | None = None,
) -> bytes:
    """Build a reportlab Form 26AS PDF with PART A (salary TDS) and PART D (refund).

    Parameters
    ----------
    pan:
        Employee PAN (10-character string).
    ay:
        Assessment year in "YYYY-YY" format.
    employer_tan:
        TAN of the employer (10-character string).
    tds_salary_amount:
        Gross salary amount in rupees.
    tds_salary_deducted:
        TDS deducted on salary in rupees.  This value appears in the PART A table
        and is read back by the parser for the cross-document test.
    """
    # Format amounts with Indian comma notation
    def _fmt(n: int) -> str:
        # Simple formatter: just use comma-separated thousands for test purposes
        return f"{n:,}"

    tds_salary_deposited = tds_salary_deducted  # assume fully deposited

    story: list = [
        _heading1("FORM 26AS"),
        _para("Annual Tax Credit Statement under Section 203AA"),
        _para(f"PAN: {pan}"),
        _para(f"Assessment Year: {ay}"),
        _para("Name: Rajesh Kumar"),
        _spacer(),
        # ----------------------------------------------------------------
        # PART A — TDS deducted on salary
        # ----------------------------------------------------------------
        _heading2("PART A"),
        _para("Details of Tax Deducted at Source (TDS) on Salary [u/s 192]"),
        _spacer(),
        _data_table(
            [
                [
                    "Sr. No.",
                    "TAN of Deductor",
                    "Name of Deductor",
                    "Amount Paid",
                    "Tax Deducted",
                    "Tax Deposited",
                ],
                [
                    "1",
                    employer_tan,
                    "Acme Software Pvt Ltd",
                    _fmt(tds_salary_amount),
                    _fmt(tds_salary_deducted),
                    _fmt(tds_salary_deposited),
                ],
            ],
            col_widths=[2 * cm, 3.5 * cm, 6 * cm, 4 * cm, 4 * cm, 4 * cm],
        ),
        _spacer(),
        PageBreak(),
        # ----------------------------------------------------------------
        # PART D — Refunds
        # ----------------------------------------------------------------
        _heading2("PART D"),
        _para("Details of Refunds"),
        _spacer(),
        _data_table(
            [
                [
                    "Sr. No.",
                    "Assessment Year",
                    "Mode",
                    "Amount of Refund",
                    "Interest",
                    "Date of Payment",
                ],
                [
                    "1",
                    ay,
                    "ECS",
                    "15,000",
                    "500",
                    "15-Aug-2025",
                ],
            ],
            col_widths=[2 * cm, 4 * cm, 3 * cm, 4 * cm, 3.5 * cm, 4 * cm],
        ),
        _spacer(),
    ]

    return _build_pdf(story, password=password)
