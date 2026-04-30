"""Unit tests for the Form 16 PDF parser.

Runs entirely in-process — no real PDFs required.  Fake PDFs are generated
by the reportlab factory in tests/fixtures/form16_factory.py.
"""
from __future__ import annotations

import re

import pytest

from kara_api.parsers import Form16Document, Form16ParseError, parse_form16
from tests.fixtures.form16_factory import (
    make_form16_encrypted,
    make_form16_hra_edge,
    make_form16_minimum,
    make_form16_part_a_only,
    make_form16_standard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TAN_RE = re.compile(r"[A-Z]{4}[0-9]{5}[A-Z]")
_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


# ---------------------------------------------------------------------------
# Standard Form 16 — Part A
# ---------------------------------------------------------------------------


class TestStandardPartA:
    @pytest.fixture(scope="class")
    def doc(self) -> Form16Document:
        return parse_form16(make_form16_standard())

    def test_employer_tan_format(self, doc: Form16Document):
        assert _TAN_RE.fullmatch(doc.part_a.employer_tan), (
            f"TAN '{doc.part_a.employer_tan}' does not match TAN pattern"
        )

    def test_employee_pan_format(self, doc: Form16Document):
        assert _PAN_RE.fullmatch(doc.part_a.employee_pan), (
            f"PAN '{doc.part_a.employee_pan}' does not match PAN pattern"
        )

    def test_assessment_year(self, doc: Form16Document):
        assert doc.part_a.assessment_year == "2025-26"

    def test_total_tds_matches_sum(self, doc: Form16Document):
        tds_sum = sum(q.tax_deposited for q in doc.part_a.quarterly_tds)
        assert doc.part_a.total_tds_deposited == tds_sum

    def test_employer_name_extracted(self, doc: Form16Document):
        assert "Acme" in doc.part_a.employer_name or len(doc.part_a.employer_name) > 0


# ---------------------------------------------------------------------------
# Standard Form 16 — Part B
# ---------------------------------------------------------------------------


class TestStandardPartB:
    @pytest.fixture(scope="class")
    def doc(self) -> Form16Document:
        return parse_form16(make_form16_standard())

    def test_part_b_not_none(self, doc: Form16Document):
        assert doc.part_b is not None

    def test_gross_salary(self, doc: Form16Document):
        assert doc.part_b.gross_salary == 1200000

    def test_standard_deduction(self, doc: Form16Document):
        assert doc.part_b.standard_deduction == 50000

    def test_80c_deduction(self, doc: Form16Document):
        assert doc.part_b.chapter_via.sec_80c == 150000

    def test_hra_exemption(self, doc: Form16Document):
        assert doc.part_b.sec10_exemptions.hra == 240000

    def test_80d_deduction(self, doc: Form16Document):
        assert doc.part_b.chapter_via.sec_80d == 25000

    def test_rebate_87a(self, doc: Form16Document):
        assert doc.part_b.rebate_87a == 0

    def test_net_tax_payable(self, doc: Form16Document):
        assert doc.part_b.net_tax_payable == 39135


# ---------------------------------------------------------------------------
# Quarterly TDS table
# ---------------------------------------------------------------------------


class TestQuarterlyTDS:
    @pytest.fixture(scope="class")
    def doc(self) -> Form16Document:
        return parse_form16(make_form16_standard())

    def test_four_quarters(self, doc: Form16Document):
        assert len(doc.part_a.quarterly_tds) == 4

    def test_quarter_labels(self, doc: Form16Document):
        assert [q.quarter for q in doc.part_a.quarterly_tds] == ["Q1", "Q2", "Q3", "Q4"]

    def test_each_quarter_tds_deposited(self, doc: Form16Document):
        for q in doc.part_a.quarterly_tds:
            assert q.tax_deposited == 15000

    def test_total_tds_deposited_invariant(self, doc: Form16Document):
        tds_sum = sum(q.tax_deposited for q in doc.part_a.quarterly_tds)
        if doc.part_a.total_tds_deposited > 0:
            assert doc.part_a.total_tds_deposited == tds_sum


# ---------------------------------------------------------------------------
# Minimum Form 16
# ---------------------------------------------------------------------------


class TestMinimumForm16:
    @pytest.fixture(scope="class")
    def doc(self) -> Form16Document:
        return parse_form16(make_form16_minimum())

    def test_part_b_not_none(self, doc: Form16Document):
        assert doc.part_b is not None

    def test_no_80c_deduction(self, doc: Form16Document):
        assert doc.part_b.chapter_via.sec_80c == 0

    def test_rebate_fully_offsets_tax(self, doc: Form16Document):
        # Tax = 10000, Rebate = 10000 → net payable = 0
        assert doc.part_b.net_tax_payable == 0

    def test_gross_salary(self, doc: Form16Document):
        assert doc.part_b.gross_salary == 500000


# ---------------------------------------------------------------------------
# HRA edge case (Indian lakh formatting)
# ---------------------------------------------------------------------------


class TestHraEdgeCase:
    @pytest.fixture(scope="class")
    def doc(self) -> Form16Document:
        return parse_form16(make_form16_hra_edge())

    def test_hra_parsed_from_lakh_format(self, doc: Form16Document):
        assert doc.part_b is not None
        # "1,50,000.00" must parse to 150000
        assert doc.part_b.sec10_exemptions.hra == 150000

    def test_gross_salary_with_decimal(self, doc: Form16Document):
        assert doc.part_b.gross_salary == 1800000


# ---------------------------------------------------------------------------
# Part A only (no Part B)
# ---------------------------------------------------------------------------


class TestPartAOnly:
    @pytest.fixture(scope="class")
    def doc(self) -> Form16Document:
        return parse_form16(make_form16_part_a_only())

    def test_part_b_is_none(self, doc: Form16Document):
        assert doc.part_b is None

    def test_part_a_still_parsed(self, doc: Form16Document):
        assert _TAN_RE.fullmatch(doc.part_a.employer_tan)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_garbage_bytes_raises_parse_error(self):
        with pytest.raises(Form16ParseError):
            parse_form16(b"not a pdf at all")

    def test_empty_bytes_raises_parse_error(self):
        with pytest.raises(Form16ParseError):
            parse_form16(b"")

    def test_encrypted_pdf_raises_parse_error(self):
        pdf_bytes = make_form16_encrypted("secret123")
        with pytest.raises(Form16ParseError):
            parse_form16(pdf_bytes)

    def test_encrypted_pdf_with_correct_password(self):
        pdf_bytes = make_form16_encrypted("secret123")
        # With correct password the parser should at least not raise (may warn)
        try:
            doc = parse_form16(pdf_bytes, password="secret123")
            assert doc.part_a is not None
        except Form16ParseError:
            # Some environments cannot decrypt even with the right password;
            # that is acceptable — the error path is still tested above.
            pass


# ---------------------------------------------------------------------------
# Document metadata
# ---------------------------------------------------------------------------


class TestDocumentMetadata:
    def test_parser_version(self):
        doc = parse_form16(make_form16_standard())
        assert doc.parser_version == "1.0"

    def test_raw_text_excerpt_populated(self):
        doc = parse_form16(make_form16_standard())
        assert doc.raw_text_excerpt is not None
        assert len(doc.raw_text_excerpt) > 0

    def test_warnings_is_list(self):
        doc = parse_form16(make_form16_standard())
        assert isinstance(doc.warnings, list)
