"""Reportlab-based fake Form 16 PDF generator.

Each factory function returns ``bytes`` containing a valid (or intentionally
broken) PDF that the Form 16 parser must handle.  Labels are chosen to match
LABEL_MAP in ``kara_api.parsers.form16`` exactly so the parser can extract
every field.
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
# Shared helpers
# ---------------------------------------------------------------------------


def _build_pdf(story: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Form 16")
    doc.build(story)
    return buf.getvalue()


def _heading(text: str) -> Paragraph:
    return Paragraph(f"<b>{text}</b>", _H2)


def _para(text: str) -> Paragraph:
    return Paragraph(text, _NORMAL)


def _spacer() -> Spacer:
    return Spacer(1, 0.3 * cm)


def _part_a_header_block(
    *,
    employer_name: str = "Acme Software Pvt Ltd",
    employer_address: str = "123 Tech Park, Pune - 411001",
    employer_tan: str = "PUNE12345F",
    employer_pan: str = "AABCA1234C",
    employee_name: str = "Rajesh Kumar",
    employee_pan: str = "ABCDE1234F",
    assessment_year: str = "2025-26",
    period_from: str = "01/04/2024",
    period_to: str = "31/03/2025",
) -> list:
    """Return a list of platypus elements forming a Part A header."""
    return [
        _heading("FORM NO. 16"),
        _para("[See rule 31(1)(a)]"),
        _spacer(),
        _heading("PART A"),
        _para(f"Name of Employer: {employer_name}"),
        _para(f"Address of Employer: {employer_address}"),
        _para(f"TAN of Employer: {employer_tan}"),
        _para(f"PAN of Employer: {employer_pan}"),
        _para(f"Name of Employee: {employee_name}"),
        _para(f"PAN of Employee: {employee_pan}"),
        _para(f"Assessment Year: {assessment_year}"),
        _para(f"Period of Employment: {period_from} to {period_to}"),
        _spacer(),
    ]


def _quarterly_tds_table(
    rows: list[tuple[str, str, int, int, int]],
) -> Table:
    """Build a quarterly TDS table.

    Each row in *rows*: (quarter, receipt_no, amount_paid, tax_deducted, tax_deposited).
    """
    headers = [
        "Quarter",
        "Receipt Numbers",
        "Amount paid/credited",
        "Tax Deducted",
        "Tax Deposited",
    ]
    data = [headers]
    for q, rcpt, amt, ded, dep in rows:
        data.append([q, rcpt, f"{amt:,}", f"{ded:,}", f"{dep:,}"])

    tbl = Table(data, colWidths=[2 * cm, 4 * cm, 4 * cm, 4 * cm, 4 * cm])
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


def _part_b_table(rows: list[tuple[str, str]]) -> Table:
    """Build a two-column label/amount table for Part B."""
    data = [["Description", "Amount (Rs)"]]
    for label, amount in rows:
        data.append([label, amount])

    tbl = Table(data, colWidths=[12 * cm, 5 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    return tbl


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def make_form16_standard() -> bytes:
    """Full Part A + Part B.

    Gross salary 12,00,000. 80C 1,50,000. HRA exempt 2,40,000.
    Standard deduction 50,000.
    """
    tds_rows = [
        ("Q1", "ABCD1234", 300000, 15000, 15000),
        ("Q2", "ABCD5678", 300000, 15000, 15000),
        ("Q3", "ABCD9012", 300000, 15000, 15000),
        ("Q4", "ABCD3456", 300000, 15000, 15000),
    ]

    part_b_rows = [
        ("Gross Salary", "12,00,000"),
        ("Salary as per provisions contained in section 17(1)", "12,00,000"),
        ("Value of perquisites under section 17(2)", "0"),
        ("Profits in lieu of salary under section 17(3)", "0"),
        ("House Rent Allowance", "2,40,000"),
        ("Leave Travel Concession", "0"),
        ("Standard Deduction under section 16(ia)", "50,000"),
        ("Professional Tax", "2,400"),
        ("Income chargeable under the head Salaries", "9,07,600"),
        ("Gross Total Income", "9,07,600"),
        ("Deduction in respect of life insurance", "1,50,000"),
        ("Deduction in respect of health insurance", "25,000"),
        ("Deduction under section 80CCD(1B)", "50,000"),
        ("Deduction under section 80CCD(2)", "0"),
        ("Aggregate of deductible amount under Chapter VI-A", "2,25,000"),
        ("Total Income", "6,82,600"),
        ("Tax on Total Income", "37,630"),
        ("Rebate under section 87A", "0"),
        ("Surcharge", "0"),
        ("Health and Education Cess", "1,505"),
        ("Tax Payable", "39,135"),
        ("Relief under section 89", "0"),
        ("Net Tax Payable", "39,135"),
    ]

    story = (
        _part_a_header_block()
        + [_quarterly_tds_table(tds_rows), _spacer(), PageBreak()]
        + [
            _heading("PART B"),
            _para("(Annexure)"),
            _spacer(),
            _part_b_table(part_b_rows),
        ]
    )
    return _build_pdf(story)


def make_form16_minimum() -> bytes:
    """Only mandatory fields.  Zero allowances. New regime (no Chapter VI-A)."""
    tds_rows = [
        ("Q1", "MIN001", 0, 0, 0),
        ("Q2", "MIN002", 0, 0, 0),
        ("Q3", "MIN003", 0, 0, 0),
        ("Q4", "MIN004", 0, 0, 0),
    ]

    part_b_rows = [
        ("Gross Salary", "5,00,000"),
        ("Salary as per provisions contained in section 17(1)", "5,00,000"),
        ("Standard Deduction under section 16(ia)", "50,000"),
        ("Income chargeable under the head Salaries", "4,50,000"),
        ("Gross Total Income", "4,50,000"),
        ("Total Income", "4,50,000"),
        ("Tax on Total Income", "10,000"),
        ("Rebate under section 87A", "10,000"),
        ("Surcharge", "0"),
        ("Health and Education Cess", "0"),
        ("Tax Payable", "0"),
        ("Relief under section 89", "0"),
        ("Net Tax Payable", "0"),
    ]

    story = (
        _part_a_header_block(
            employer_name="Minimal Corp Ltd",
            employer_tan="MUMB00001A",
            employee_pan="ZZZZZ9999Z",
        )
        + [_quarterly_tds_table(tds_rows), _spacer(), PageBreak()]
        + [
            _heading("PART B"),
            _spacer(),
            _part_b_table(part_b_rows),
        ]
    )
    return _build_pdf(story)


def make_form16_hra_edge() -> bytes:
    """HRA with Indian lakh formatting e.g. 1,50,000.00.  Tests to_int."""
    tds_rows = [
        ("Q1", "HRA001", 450000, 5000, 5000),
        ("Q2", "HRA002", 450000, 5000, 5000),
        ("Q3", "HRA003", 450000, 5000, 5000),
        ("Q4", "HRA004", 450000, 5000, 5000),
    ]

    # Deliberately use Indian lakh formatting with decimals for the HRA amount
    part_b_rows = [
        ("Gross Salary", "18,00,000.00"),
        ("Salary as per provisions contained in section 17(1)", "18,00,000.00"),
        ("House Rent Allowance", "1,50,000.00"),
        ("Standard Deduction under section 16(ia)", "50,000.00"),
        ("Professional Tax", "2,400.00"),
        ("Income chargeable under the head Salaries", "16,47,600.00"),
        ("Gross Total Income", "16,47,600.00"),
        ("Total Income", "16,47,600.00"),
        ("Tax on Total Income", "2,25,000.00"),
        ("Surcharge", "0.00"),
        ("Health and Education Cess", "9,000.00"),
        ("Tax Payable", "2,34,000.00"),
        ("Relief under section 89", "0.00"),
        ("Net Tax Payable", "2,34,000.00"),
    ]

    story = (
        _part_a_header_block(
            employer_name="HRA Edge Employers",
            employer_tan="HYDH11111B",
            employee_pan="HRAXXX1234Y",
        )
        + [_quarterly_tds_table(tds_rows), _spacer(), PageBreak()]
        + [
            _heading("PART B"),
            _spacer(),
            _part_b_table(part_b_rows),
        ]
    )
    return _build_pdf(story)


def make_form16_part_a_only() -> bytes:
    """PDF with PART A but no PART B or Annexure page."""
    tds_rows = [
        ("Q1", "AOX001", 200000, 10000, 10000),
        ("Q2", "AOX002", 200000, 10000, 10000),
        ("Q3", "AOX003", 200000, 10000, 10000),
        ("Q4", "AOX004", 200000, 10000, 10000),
    ]

    story = _part_a_header_block(
        employer_name="Part A Only Ltd",
        employer_tan="DELD11111C",
        employee_pan="PARTX1234A",
    ) + [_quarterly_tds_table(tds_rows)]
    return _build_pdf(story)


def make_form16_encrypted(password: str) -> bytes:
    """Encrypted PDF.

    Uses reportlab canvas encryption so pdfplumber raises a password error.
    """
    buf = io.BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(buf, pagesize=A4, encrypt=password)
    c.drawString(100, 750, "FORM NO. 16 — PART A")
    c.drawString(100, 730, "Name of Employer: Secret Corp")
    c.drawString(100, 710, "TAN: SECA12345B")
    c.drawString(100, 690, "PAN of Employee: SECRX1234A")
    c.drawString(100, 670, "Assessment Year: 2025-26")
    c.save()
    return buf.getvalue()
