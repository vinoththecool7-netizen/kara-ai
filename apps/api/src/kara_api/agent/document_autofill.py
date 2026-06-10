"""Document auto-fill: maps parsed document fields onto ProfileBuilder slots.

Three pure functions — one per document type — that apply extracted data
onto an existing ProfileBuilder and return a diff describing what changed.

Amounts stored in ProfileBuilder are always in **rupees**.
AIS and 26AS parsers store monetary values in **paise**, so we divide by 100.
Form 16 parser stores monetary values directly in **rupees**.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from kara_api.agent.profile_builder import ProfileBuilder
    from kara_api.parsers.ais import AISDocument
    from kara_api.parsers.form16 import Form16Document
    from kara_api.parsers.twenty_six_as import Form26ASDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Diff model
# ---------------------------------------------------------------------------


class AutofillDiff(BaseModel):
    """Describes what changed in the ProfileBuilder after applying a document."""

    slots_added: dict[str, Any] = {}
    # slot_name -> [old_value, new_value]
    slots_overridden: dict[str, list[Any]] = {}
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _set_slot(
    builder: ProfileBuilder,
    diff: AutofillDiff,
    slot_name: str,
    value: Any,
) -> None:
    """Set *slot_name* on *builder*, recording adds and overrides in *diff*."""
    existing = builder.get_slot(slot_name)
    if existing is None:
        builder.add_slot(slot_name, value)
        diff.slots_added[slot_name] = value
    elif existing != value:
        builder.add_slot(slot_name, value)
        diff.slots_overridden[slot_name] = [existing, value]
    # If existing == value, no-op (no change recorded)


def _add_to_slot(
    builder: ProfileBuilder,
    diff: AutofillDiff,
    slot_name: str,
    amount: int,
) -> None:
    """Add *amount* to an existing numeric slot (or create it with *amount*)."""
    existing = builder.get_slot(slot_name) or 0
    new_value = existing + amount
    if existing == 0:
        builder.add_slot(slot_name, new_value)
        diff.slots_added[slot_name] = new_value
    else:
        builder.add_slot(slot_name, new_value)
        diff.slots_overridden[slot_name] = [existing, new_value]


# ---------------------------------------------------------------------------
# Form 16 → ProfileBuilder
# ---------------------------------------------------------------------------


def apply_form16(
    builder: ProfileBuilder,
    doc: Form16Document,
) -> AutofillDiff:
    """Map Form16Document fields onto *builder* slots.

    Form 16 stores amounts in rupees, so no conversion is needed.

    Returns
    -------
    AutofillDiff
        What slots were added or overridden.
    """
    diff = AutofillDiff()

    part_a = doc.part_a
    part_b = doc.part_b

    # --- Part A fields ---
    # employer_tan → metadata
    if part_a.employer_tan and part_a.employer_tan != "UNKNOWN0000X":
        _set_slot(builder, diff, "employer_tan", part_a.employer_tan)

    # employee_pan → metadata
    if part_a.employee_pan and part_a.employee_pan != "UNKNOWN0000X":
        _set_slot(builder, diff, "pan", part_a.employee_pan)

    # employer_name → metadata
    if part_a.employer_name and part_a.employer_name != "Unknown Employer":
        _set_slot(builder, diff, "employer_name", part_a.employer_name)

    # total_tds_deposited → internal tds_form16 (rupees from Form 16)
    if part_a.total_tds_deposited:
        _set_slot(builder, diff, "tds_form16", part_a.total_tds_deposited)

    # assessment_year → metadata
    if part_a.assessment_year:
        _set_slot(builder, diff, "assessment_year", part_a.assessment_year)

    # --- Part B fields ---
    if part_b is None:
        diff.warnings.append("Form 16 Part B not found; salary/deduction fields not set.")
        _check_tds_reconciliation(builder, diff)
        return diff

    # gross_salary → gross_salary slot
    if part_b.gross_salary:
        _set_slot(builder, diff, "gross_salary", part_b.gross_salary)

    # standard_deduction → metadata only (not a TaxProfile slot for user to supply)
    if part_b.standard_deduction:
        _set_slot(builder, diff, "standard_deduction_form16", part_b.standard_deduction)

    # Chapter VI-A deductions → deduction slots
    via = part_b.chapter_via

    if via.sec_80c:
        _set_slot(builder, diff, "section_80c", via.sec_80c)

    if via.sec_80d:
        _set_slot(builder, diff, "section_80d", via.sec_80d)

    if via.sec_80ccd_1b:
        _set_slot(builder, diff, "section_80ccd_1b", via.sec_80ccd_1b)

    if via.sec_80ccd_2:
        _set_slot(builder, diff, "section_80ccd_2", via.sec_80ccd_2)

    if via.sec_80e:
        _set_slot(builder, diff, "section_80e", via.sec_80e)

    if via.sec_80g:
        _set_slot(builder, diff, "section_80g", via.sec_80g)

    if via.sec_80tta:
        _set_slot(builder, diff, "section_80tta", via.sec_80tta)

    if via.sec_80ttb:
        _set_slot(builder, diff, "section_80ttb", via.sec_80ttb)

    _check_tds_reconciliation(builder, diff)
    return diff


# ---------------------------------------------------------------------------
# AIS → ProfileBuilder
# ---------------------------------------------------------------------------


def apply_ais(
    builder: ProfileBuilder,
    doc: AISDocument,
) -> AutofillDiff:
    """Map AISDocument fields onto *builder* slots.

    AIS stores amounts in **paise**; divide by 100 to get rupees.

    Returns
    -------
    AutofillDiff
        What slots were added or overridden.
    """
    diff = AutofillDiff()

    # --- PAN ---
    if doc.pan:
        _set_slot(builder, diff, "pan", doc.pan)

    # --- Interest (savings + FD) → other_income (rupees) ---
    total_interest_paise = sum(e.amount for e in doc.interest_savings) + sum(
        e.amount for e in doc.interest_fd
    )
    if total_interest_paise:
        interest_rupees = total_interest_paise // 100
        _add_to_slot(builder, diff, "other_income", interest_rupees)

    # --- Dividends → other_income (rupees) ---
    total_dividends_paise = sum(e.amount for e in doc.dividends)
    if total_dividends_paise:
        dividends_rupees = total_dividends_paise // 100
        _add_to_slot(builder, diff, "other_income", dividends_rupees)

    # --- Capital gains (securities) → warning only (no cost basis) ---
    total_security_sales = len(doc.security_sales)
    total_security_purchases = len(doc.security_purchases)
    if total_security_sales or total_security_purchases:
        sale_value_paise = sum(e.value for e in doc.security_sales)
        purchase_value_paise = sum(e.value for e in doc.security_purchases)
        diff.warnings.append(
            f"AIS reports {total_security_sales} security sale(s) totaling "
            f"₹{sale_value_paise // 100:,} and {total_security_purchases} purchase(s) "
            f"totaling ₹{purchase_value_paise // 100:,}. "
            "Capital gains require cost-basis verification — not auto-filled. "
            "Please review and enter capital gains manually."
        )
        # Store raw metadata for reference
        _set_slot(builder, diff, "ais_security_sales_count", total_security_sales)
        _set_slot(builder, diff, "ais_security_purchases_count", total_security_purchases)

    # --- Mutual fund redemptions → warning only ---
    if doc.mutual_fund_redemptions:
        mf_value_paise = sum(e.amount for e in doc.mutual_fund_redemptions)
        diff.warnings.append(
            f"AIS reports {len(doc.mutual_fund_redemptions)} mutual fund redemption(s) "
            f"totaling ₹{mf_value_paise // 100:,}. "
            "Capital gains from MF redemptions require NAV history — not auto-filled."
        )

    _check_tds_reconciliation(builder, diff)
    return diff


# ---------------------------------------------------------------------------
# Form 26AS → ProfileBuilder
# ---------------------------------------------------------------------------


def apply_26as(
    builder: ProfileBuilder,
    doc: Form26ASDocument,
) -> AutofillDiff:
    """Map Form26ASDocument fields onto *builder* slots.

    26AS stores amounts in **paise**; divide by 100 to get rupees.

    Returns
    -------
    AutofillDiff
        What slots were added or overridden.
    """
    diff = AutofillDiff()

    # --- PAN ---
    if doc.pan:
        _set_slot(builder, diff, "pan", doc.pan)

    # --- TDS on salary → tds_26as (rupees) ---
    total_tds_salary_paise = doc.totals.total_tds_salary
    if total_tds_salary_paise:
        tds_salary_rupees = total_tds_salary_paise // 100
        _set_slot(builder, diff, "tds_26as", tds_salary_rupees)

    # --- Advance tax paid → metadata (rupees) ---
    advance_tax_paise = sum(e.amount for e in doc.advance_tax_paid)
    if advance_tax_paise:
        advance_tax_rupees = advance_tax_paise // 100
        _set_slot(builder, diff, "advance_tax_paid", advance_tax_rupees)

    # --- Self-assessment tax → metadata (rupees) ---
    self_assessment_paise = sum(e.amount for e in doc.self_assessment_tax)
    if self_assessment_paise:
        self_assessment_rupees = self_assessment_paise // 100
        _set_slot(builder, diff, "self_assessment_tax", self_assessment_rupees)

    _check_tds_reconciliation(builder, diff)
    return diff


# ---------------------------------------------------------------------------
# TDS reconciliation check (called after each document application)
# ---------------------------------------------------------------------------


def _check_tds_reconciliation(
    builder: ProfileBuilder,
    diff: AutofillDiff,
) -> None:
    """If both tds_form16 and tds_26as are set and differ by > ₹100, warn."""
    form16_tds = builder.get_slot("tds_form16")
    as26_tds = builder.get_slot("tds_26as")

    if form16_tds is not None and as26_tds is not None:
        delta = abs(form16_tds - as26_tds)
        if delta > 100:
            warning = (
                f"TDS reconciliation: Form 16 reported ₹{form16_tds:,}, "
                f"26AS reports ₹{as26_tds:,}; using 26AS as canonical."
            )
            # Only add the warning if it's not already there
            if warning not in diff.warnings:
                diff.warnings.append(warning)
