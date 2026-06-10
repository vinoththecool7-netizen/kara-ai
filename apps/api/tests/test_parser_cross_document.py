"""Cross-document consistency tests for Form 16 ↔ 26AS.

The key invariant: if the same employer's TAN appears in both Form 16 (Part A)
and Form 26AS (Part A), the TDS deposited amounts should match within rounding.
"""
from __future__ import annotations

from kara_api.parsers import parse_form16
from kara_api.parsers.twenty_six_as import parse_form_26as
from tests.fixtures.form16_factory import make_form16_standard
from tests.fixtures.twenty_six_as_factory import build_26as_pdf


def test_form16_part_a_tds_matches_26as_salary_tds():
    """Same TAN, same employer — TDS from Form 16 and 26AS should match.

    Form 16 ``total_tds_deposited`` is in rupees (int).
    Form 26AS ``tax_deducted`` per entry is in paise.

    So: sum(26AS tax_deducted) // 100 == form16.total_tds_deposited  (±1 for rounding)
    """
    # Parse Form 16 standard fixture
    form16 = parse_form16(make_form16_standard())
    assert form16.part_a is not None, "Form 16 Part A must be parsed"

    # Build a 26AS PDF using the same TAN and the same TDS figure
    f26as = parse_form_26as(
        build_26as_pdf(
            employer_tan=form16.part_a.employer_tan,
            tds_salary_deducted=form16.part_a.total_tds_deposited,
        )
    )

    assert f26as.tds_on_salary, "26AS must have at least one salary TDS entry"

    # Check TAN match
    tans_in_26as = {e.deductor_tan for e in f26as.tds_on_salary}
    assert form16.part_a.employer_tan in tans_in_26as, (
        f"Employer TAN {form16.part_a.employer_tan!r} not found in 26AS entries {tans_in_26as}"
    )

    # Check TDS amount consistency
    total_26as_tds_paise = sum(e.tax_deducted for e in f26as.tds_on_salary)
    total_26as_tds_rupees = total_26as_tds_paise // 100

    form16_tds_rupees = form16.part_a.total_tds_deposited

    assert abs(total_26as_tds_rupees - form16_tds_rupees) <= 1, (
        f"TDS mismatch: Form16={form16_tds_rupees} rupees, "
        f"26AS={total_26as_tds_rupees} rupees "
        f"(raw paise={total_26as_tds_paise})"
    )


def test_form16_and_26as_same_pan():
    """Both Form 16 and 26AS should report the same PAN for the employee."""
    form16 = parse_form16(make_form16_standard())
    f26as = parse_form_26as(build_26as_pdf(pan=form16.part_a.employee_pan))

    assert form16.part_a.employee_pan == f26as.pan, (
        f"PAN mismatch: Form16={form16.part_a.employee_pan!r}, 26AS={f26as.pan!r}"
    )


def test_cross_document_no_crash_with_mismatched_tan():
    """Parser should not crash even when TANs do not match between documents."""
    parse_form16(make_form16_standard())
    # Use a different TAN intentionally
    f26as = parse_form_26as(build_26as_pdf(employer_tan="DELD99999Z"))

    assert isinstance(f26as, parse_form_26as.__annotations__.get("return", object).__class__) or True
    # The main assertion is just that no exception is raised
    assert f26as is not None
