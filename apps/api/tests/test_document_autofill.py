"""Tests for kara_api.agent.document_autofill — pure autofill functions."""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from kara_api.agent.document_autofill import (
    AutofillDiff,
    apply_26as,
    apply_ais,
    apply_form16,
)
from kara_api.agent.profile_builder import ProfileBuilder
from kara_api.parsers.ais import (
    AISDocument,
    AISTotals,
    DividendEntry,
    InterestEntry,
    SecurityTxn,
)
from kara_api.parsers.form16 import (
    ChapterVIADeductions,
    Form16Document,
    Form16PartA,
    Form16PartB,
    Sec10Exemptions,
)
from kara_api.parsers.twenty_six_as import (
    AdvanceTaxEntry,
    Form26ASDocument,
    Form26ASTotals,
    SelfAssessmentEntry,
    TDSSalaryEntry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_form16(
    gross_salary: int = 1_200_000,
    sec_80c: int = 150_000,
    sec_80d: int = 25_000,
    sec_80ccd_1b: int = 50_000,
    sec_80ccd_2: int = 0,
    total_tds: int = 60_000,
    employer_tan: str = "AABC12345D",
    employee_pan: str = "ABCDE1234F",
    employer_name: str = "Acme Corp",
) -> Form16Document:
    part_a = Form16PartA(
        employer_name=employer_name,
        employer_tan=employer_tan,
        employee_name="Test Employee",
        employee_pan=employee_pan,
        assessment_year="2025-26",
        total_tds_deposited=total_tds,
    )
    chapter_via = ChapterVIADeductions(
        sec_80c=sec_80c,
        sec_80d=sec_80d,
        sec_80ccd_1b=sec_80ccd_1b,
        sec_80ccd_2=sec_80ccd_2,
    )
    part_b = Form16PartB(
        gross_salary=gross_salary,
        standard_deduction=50_000,
        chapter_via=chapter_via,
    )
    return Form16Document(part_a=part_a, part_b=part_b)


def _make_ais(
    interest_savings_paise: int = 0,
    interest_fd_paise: int = 0,
    dividends_paise: int = 0,
    security_sales: int = 0,
    security_purchases: int = 0,
) -> AISDocument:
    doc = AISDocument(source="json", pan="ABCDE1234F", assessment_year="2025-26")

    if interest_savings_paise:
        doc.interest_savings = [
            InterestEntry(payer_name="SBI", account_type="savings", amount=interest_savings_paise)
        ]
    if interest_fd_paise:
        doc.interest_fd = [
            InterestEntry(payer_name="HDFC", account_type="fd", amount=interest_fd_paise)
        ]
    if dividends_paise:
        doc.dividends = [DividendEntry(payer_name="Infosys Ltd", amount=dividends_paise)]

    for _ in range(security_sales):
        doc.security_sales.append(
            SecurityTxn(scrip_name="RELIANCE", txn_type="sell", value=100_000_00)
        )
    for _ in range(security_purchases):
        doc.security_purchases.append(
            SecurityTxn(scrip_name="RELIANCE", txn_type="buy", value=80_000_00)
        )

    doc.totals = AISTotals(
        total_interest=interest_savings_paise + interest_fd_paise,
        total_dividends=dividends_paise,
    )
    return doc


def _make_26as(
    tds_salary_paise: int = 0,
    advance_tax_paise: int = 0,
    self_assessment_paise: int = 0,
) -> Form26ASDocument:
    doc = Form26ASDocument(source="pdf", pan="ABCDE1234F", assessment_year="2025-26")

    if tds_salary_paise:
        doc.tds_on_salary = [
            TDSSalaryEntry(
                deductor_name="Acme Corp",
                deductor_tan="AABC12345D",
                tax_deducted=tds_salary_paise,
                tax_deposited=tds_salary_paise,
            )
        ]

    if advance_tax_paise:
        doc.advance_tax_paid = [
            AdvanceTaxEntry(bsr_code="0001234", challan_serial="001", amount=advance_tax_paise)
        ]

    if self_assessment_paise:
        doc.self_assessment_tax = [
            SelfAssessmentEntry(
                bsr_code="0001234", challan_serial="002", amount=self_assessment_paise
            )
        ]

    doc.totals = Form26ASTotals(
        total_tds_salary=tds_salary_paise,
        total_advance_tax=advance_tax_paise,
        total_self_assessment=self_assessment_paise,
    )
    return doc


# ---------------------------------------------------------------------------
# Form 16 tests
# ---------------------------------------------------------------------------


class TestApplyForm16:
    def test_sets_gross_salary(self):
        builder = ProfileBuilder()
        doc = _make_form16(gross_salary=1_200_000)
        apply_form16(builder, doc)
        assert builder.get_slot("gross_salary") == 1_200_000

    def test_sets_deductions(self):
        builder = ProfileBuilder()
        doc = _make_form16(sec_80c=150_000, sec_80d=25_000, sec_80ccd_1b=50_000)
        apply_form16(builder, doc)
        assert builder.get_slot("section_80c") == 150_000
        assert builder.get_slot("section_80d") == 25_000
        assert builder.get_slot("section_80ccd_1b") == 50_000

    def test_sets_pan_and_tan(self):
        builder = ProfileBuilder()
        doc = _make_form16(employee_pan="ABCDE1234F", employer_tan="AABC12345D")
        apply_form16(builder, doc)
        assert builder.get_slot("pan") == "ABCDE1234F"
        assert builder.get_slot("employer_tan") == "AABC12345D"

    def test_sets_tds_form16(self):
        builder = ProfileBuilder()
        doc = _make_form16(total_tds=60_000)
        apply_form16(builder, doc)
        assert builder.get_slot("tds_form16") == 60_000

    def test_tracks_slots_added_in_diff(self):
        builder = ProfileBuilder()
        doc = _make_form16(gross_salary=1_200_000, sec_80c=150_000)
        diff = apply_form16(builder, doc)
        assert "gross_salary" in diff.slots_added
        assert diff.slots_added["gross_salary"] == 1_200_000
        assert "section_80c" in diff.slots_added

    def test_tracks_slots_overridden_in_diff(self):
        builder = ProfileBuilder(initial_slots={"gross_salary": 1_000_000})
        doc = _make_form16(gross_salary=1_200_000)
        diff = apply_form16(builder, doc)
        assert "gross_salary" in diff.slots_overridden
        assert diff.slots_overridden["gross_salary"] == [1_000_000, 1_200_000]

    def test_no_override_recorded_when_value_unchanged(self):
        builder = ProfileBuilder(initial_slots={"gross_salary": 1_200_000})
        doc = _make_form16(gross_salary=1_200_000)
        diff = apply_form16(builder, doc)
        assert "gross_salary" not in diff.slots_added
        assert "gross_salary" not in diff.slots_overridden

    def test_standard_deduction_stored_as_metadata_not_income_slot(self):
        builder = ProfileBuilder()
        doc = _make_form16()
        apply_form16(builder, doc)
        # standard_deduction should NOT be stored as a profile deduction slot
        assert builder.get_slot("standard_deduction") is None
        # But should be available as metadata
        assert builder.get_slot("standard_deduction_form16") == 50_000

    def test_part_b_none_adds_warning(self):
        builder = ProfileBuilder()
        part_a = Form16PartA(
            employer_name="Acme Corp",
            employer_tan="AABC12345D",
            employee_name="Test",
            employee_pan="ABCDE1234F",
            assessment_year="2025-26",
        )
        doc = Form16Document(part_a=part_a, part_b=None)
        diff = apply_form16(builder, doc)
        assert any("Part B" in w for w in diff.warnings)

    def test_zero_deductions_not_stored(self):
        builder = ProfileBuilder()
        doc = _make_form16(sec_80c=0, sec_80d=0)
        apply_form16(builder, doc)
        assert builder.get_slot("section_80c") is None
        assert builder.get_slot("section_80d") is None


# ---------------------------------------------------------------------------
# AIS tests
# ---------------------------------------------------------------------------


class TestApplyAIS:
    def test_adds_savings_interest_to_other_income(self):
        builder = ProfileBuilder()
        doc = _make_ais(interest_savings_paise=50_000_00)  # ₹50,000 in paise
        apply_ais(builder, doc)
        assert builder.get_slot("other_income") == 50_000

    def test_adds_fd_interest_to_other_income(self):
        builder = ProfileBuilder()
        doc = _make_ais(interest_fd_paise=20_000_00)  # ₹20,000 in paise
        apply_ais(builder, doc)
        assert builder.get_slot("other_income") == 20_000

    def test_adds_dividends_to_other_income(self):
        builder = ProfileBuilder()
        doc = _make_ais(dividends_paise=10_000_00)  # ₹10,000 in paise
        apply_ais(builder, doc)
        assert builder.get_slot("other_income") == 10_000

    def test_accumulates_interest_and_dividends(self):
        builder = ProfileBuilder()
        doc = _make_ais(
            interest_savings_paise=30_000_00,
            dividends_paise=10_000_00,
        )
        apply_ais(builder, doc)
        # ₹30,000 + ₹10,000 = ₹40,000
        assert builder.get_slot("other_income") == 40_000

    def test_accumulates_on_top_of_existing_other_income(self):
        builder = ProfileBuilder(initial_slots={"other_income": 5_000})
        doc = _make_ais(interest_savings_paise=10_000_00)  # ₹10,000
        apply_ais(builder, doc)
        assert builder.get_slot("other_income") == 15_000

    def test_security_sales_adds_warning_not_slot(self):
        builder = ProfileBuilder()
        doc = _make_ais(security_sales=2, security_purchases=1)
        diff = apply_ais(builder, doc)
        assert any("capital" in w.lower() or "security" in w.lower() for w in diff.warnings)
        # Should NOT auto-set capital_gains slot
        assert builder.get_slot("capital_gains_income") is None

    def test_sets_pan(self):
        builder = ProfileBuilder()
        doc = _make_ais()
        apply_ais(builder, doc)
        assert builder.get_slot("pan") == "ABCDE1234F"

    def test_no_change_when_all_zero(self):
        builder = ProfileBuilder()
        doc = _make_ais()
        diff = apply_ais(builder, doc)
        # pan is set but no income added
        assert builder.get_slot("other_income") is None


# ---------------------------------------------------------------------------
# Form 26AS tests
# ---------------------------------------------------------------------------


class TestApply26AS:
    def test_sets_tds_26as(self):
        builder = ProfileBuilder()
        doc = _make_26as(tds_salary_paise=60_000_00)  # ₹60,000
        apply_26as(builder, doc)
        assert builder.get_slot("tds_26as") == 60_000

    def test_sets_advance_tax_paid(self):
        builder = ProfileBuilder()
        doc = _make_26as(advance_tax_paise=25_000_00)  # ₹25,000
        apply_26as(builder, doc)
        assert builder.get_slot("advance_tax_paid") == 25_000

    def test_sets_self_assessment_tax(self):
        builder = ProfileBuilder()
        doc = _make_26as(self_assessment_paise=10_000_00)  # ₹10,000
        apply_26as(builder, doc)
        assert builder.get_slot("self_assessment_tax") == 10_000

    def test_sets_pan(self):
        builder = ProfileBuilder()
        doc = _make_26as(tds_salary_paise=60_000_00)
        apply_26as(builder, doc)
        assert builder.get_slot("pan") == "ABCDE1234F"

    def test_zero_tds_not_stored(self):
        builder = ProfileBuilder()
        doc = _make_26as()
        apply_26as(builder, doc)
        assert builder.get_slot("tds_26as") is None

    def test_tracks_slots_added(self):
        builder = ProfileBuilder()
        doc = _make_26as(tds_salary_paise=60_000_00)
        diff = apply_26as(builder, doc)
        assert "tds_26as" in diff.slots_added


# ---------------------------------------------------------------------------
# Conflict / reconciliation tests
# ---------------------------------------------------------------------------


class TestConflictPolicy:
    def test_tds_reconciliation_warning_when_differ_by_more_than_100(self):
        builder = ProfileBuilder()

        # Apply Form 16 first (rupees)
        form16 = _make_form16(total_tds=60_000)
        apply_form16(builder, form16)
        assert builder.get_slot("tds_form16") == 60_000

        # Apply 26AS (paise — ₹61,000 in paise)
        as26 = _make_26as(tds_salary_paise=61_000_00)
        diff = apply_26as(builder, as26)

        assert builder.get_slot("tds_26as") == 61_000
        assert any("TDS reconciliation" in w for w in diff.warnings)

    def test_no_reconciliation_warning_when_within_100(self):
        builder = ProfileBuilder()

        form16 = _make_form16(total_tds=60_000)
        apply_form16(builder, form16)

        # ₹60,050 — only ₹50 difference, within tolerance
        as26 = _make_26as(tds_salary_paise=60_050_00)
        diff = apply_26as(builder, as26)

        assert not any("TDS reconciliation" in w for w in diff.warnings)

    def test_override_policy_records_old_and_new(self):
        builder = ProfileBuilder(initial_slots={"section_80c": 100_000})
        doc = _make_form16(sec_80c=150_000)
        diff = apply_form16(builder, doc)
        assert "section_80c" in diff.slots_overridden
        assert diff.slots_overridden["section_80c"] == [100_000, 150_000]

    def test_diff_is_pydantic_model(self):
        builder = ProfileBuilder()
        doc = _make_form16()
        diff = apply_form16(builder, doc)
        assert isinstance(diff, AutofillDiff)
        assert isinstance(diff.slots_added, dict)
        assert isinstance(diff.slots_overridden, dict)
        assert isinstance(diff.warnings, list)
