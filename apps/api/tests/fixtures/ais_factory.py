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


# ---------------------------------------------------------------------------
# Portal-layout PDF factory (real e-filing AIS structure)
# ---------------------------------------------------------------------------


def _portal_pdf(story: list, *, password: str | None = None) -> bytes:
    """Landscape variant used by the portal fixture — the real portal PDF
    uses wide tables; portrait A4 would overlap cell text and garble
    pdfplumber's extraction."""
    from reportlab.lib.pagesizes import landscape

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), title="AIS", encrypt=password,
        leftMargin=1 * cm, rightMargin=1 * cm,
    )
    doc.build(story)
    return buf.getvalue()


def _portal_table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Bordered table at a small font so long portal headers fit their cells."""
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tbl


def build_ais_portal_pdf(
    *,
    pan: str = "ABCDE1234F",
    ay: str = "2025-26",
    password: str | None = None,
    include_dividend_detail: bool = False,
) -> bytes:
    """Build a PDF replicating the real e-filing portal AIS layout.

    Unlike build_ais_pdf() (legacy "Information Category:" markers), the
    portal layout uses Part B1/B2 sections where each information item is a
    summary row (SR NO | INFORMATION CODE | DESCRIPTION | SOURCE | COUNT |
    AMOUNT) followed by a category-specific detail table.
    """
    summary_header = [
        "SR. NO.", "INFORMATION CODE", "INFORMATION DESCRIPTION",
        "INFORMATION SOURCE", "COUNT", "AMOUNT",
    ]

    story: list = [
        _heading(f"Annual Information Statement (AIS) Financial Year {ay}"),
        _para("Part A - General Information"),
        _para(f"Permanent Account Number (PAN): {pan}"),
        _para("Name: Rajesh Kumar"),
        _spacer(),
        _para("Part B1-Information relating to tax deducted or collected at source"),
        _portal_table(
            [summary_header, ["No Transactions Present", "", "", "", "", ""]],
            col_widths=[2 * cm, 3.4 * cm, 7 * cm, 7 * cm, 2.2 * cm, 3.4 * cm],
        ),
        _spacer(),
        _para("Part B2-Information relating to specified financial transaction (SFT)"),
        _para("Interest from savings bank"),
        _portal_table(
            [
                summary_header,
                ["1", "SFT-016(SB)", "Interest income (SFT-016) – Savings",
                 "HDFC BANK LIMITED (AAACH1234A.AB123)", "2", "480"],
                ["SR. NO.", "REPORTED ON", "ACCOUNT NUMBER", "ACCOUNT TYPE",
                 "INTEREST AMOUNT", "STATUS"],
                ["1", "15/04/2025", "50100123456789", "Saving", "300", "Active"],
                ["2", "15/04/2025", "50100987654321", "Saving", "180", "Active"],
            ],
            col_widths=[2 * cm, 3.4 * cm, 5.5 * cm, 5 * cm, 4 * cm, 3.4 * cm],
        ),
        _spacer(),
        _para("Sale of securities and units of mutual fund"),
        _portal_table(
            [
                summary_header,
                ["1", "SFT-18-EMF(M)", "Sale of unit of equity oriented mutual fund (RTA)",
                 "KFin Technologies Pvt. Ltd (AAACK1234B)", "3", "45,000"],
            ],
            col_widths=[2 * cm, 3.4 * cm, 7 * cm, 7 * cm, 2.2 * cm, 3.4 * cm],
        ),
        _portal_table(
            [
                ["SR. NO.", "DATE OF SALE/ TRANSFER", "SECURITY NAME (SECURITY CODE)",
                 "ASSET TYPE", "QUANTITY", "SALE PRICE PER UNIT",
                 "SALES CONSIDERATION", "COST OF ACQUISITION", "STATUS"],
                ["1", "12/06/2025", "UTI Mid Cap Fund_Direct", "Short term",
                 "10.5", "1,428.57", "15,000", "12,000", "Active"],
                ["2", "18/09/2025", "UTI Mid Cap Fund_Direct", "Short term",
                 "9.2", "1,630.43", "15,000", "13,000", "Active"],
                ["3", "05/01/2026", "UTI Mid Cap Fund_Direct", "Short term",
                 "8.8", "1,704.55", "15,000", "13,500", "Active"],
            ],
            col_widths=[1.6 * cm, 3 * cm, 5 * cm, 2.4 * cm, 2.2 * cm, 2.6 * cm,
                        3 * cm, 3 * cm, 2.2 * cm],
        ),
        _spacer(),
        _portal_table(
            [
                summary_header,
                ["1", "SFT-18-OTU(M)", "Sale of other unit (Depository)",
                 "CENTRAL DEPOSITORY SERVICES(I) LIMITED", "1", "12,000"],
                ["SR. NO.", "DATE OF SALE/ TRANSFER", "SECURITY NAME (SECURITY CODE)",
                 "ASSET TYPE", "QUANTITY", "SALE PRICE PER UNIT",
                 "SALES CONSIDERATION", "COST OF ACQUISITION", "STATUS"],
                ["1", "20/11/2025", "AXIS AMC LTD#AXIS MF-ARBITRAGE", "Short term",
                 "55.0", "218.18", "12,000", "11,500", "Active"],
            ],
            col_widths=[1.6 * cm, 3 * cm, 5.2 * cm, 2.4 * cm, 2.2 * cm, 2.6 * cm,
                        3 * cm, 3 * cm, 2.2 * cm],
        ),
        _spacer(),
        _para("Purchase of securities and units of mutual funds"),
        _portal_table(
            [
                summary_header,
                ["1", "SFT-18(Pur)", "Purchase of mutual funds (SFT - 018)",
                 "KFin Technologies Pvt. Ltd - UTI MUTUAL FUND(101)", "4", "1,20,000"],
                ["SR. NO.", "QUARTER", "CLIENT ID", "AMC NAME (CODE)", "HOLDER FLAG",
                 "TOTAL PURCHASE AMOUNT", "TOTAL SALES VALUE", "STATUS"],
                ["1", "Q4(Jan-Mar)", "123456789012", "UTI MUTUAL FUND(101)", "First",
                 "30,000", "0", "Active"],
                ["2", "Q3(Oct-Dec)", "123456789012", "UTI MUTUAL FUND(101)", "First",
                 "30,000", "0", "Active"],
                ["3", "Q2(Jul-Sep)", "123456789012", "UTI MUTUAL FUND(101)", "First",
                 "30,000", "0", "Active"],
                ["4", "Q1(Apr-Jun)", "123456789012", "UTI MUTUAL FUND(101)", "First",
                 "30,000", "0", "Active"],
            ],
            col_widths=[1.6 * cm, 3 * cm, 3.4 * cm, 5 * cm, 2.4 * cm, 3.8 * cm,
                        3 * cm, 2.2 * cm],
        ),
        _spacer(),
        _portal_table(
            [
                summary_header,
                ["1", "SFT-17(Pur)", "Purchase of securities (SFT - 017)",
                 "CENTRAL DEPOSITORY SERVICES(I) LIMITED", "1", "10,000"],
                ["SR. NO.", "QUARTER", "CLIENT ID", "HOLDER FLAG",
                 "MARKET PURCHASE", "MARKET SALES", "STATUS"],
                ["1", "-", "87654321", "First", "10,000", "0", "Active"],
            ],
            col_widths=[1.8 * cm, 3 * cm, 3.8 * cm, 3 * cm, 4 * cm,
                        3.4 * cm, 2.4 * cm],
        ),
        _spacer(),
        # Dividend has a summary row but NO detail table — exercises the
        # summary-level fallback path.
        _portal_table(
            [
                summary_header,
                ["1", "SFT-15", "Dividend income", "INFOSYS LTD", "1", "2,500"],
            ],
            col_widths=[2 * cm, 3.4 * cm, 7 * cm, 7 * cm, 2.2 * cm, 3.4 * cm],
        ),
    ]

    return _portal_pdf(story, password=password)
