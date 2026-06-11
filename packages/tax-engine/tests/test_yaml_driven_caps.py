"""Prove deduction caps are YAML-driven, not hardcoded.

Each test loads a fresh TaxComputer, mutates the in-memory YAML rule data,
and verifies the computation follows the mutated value. If a cap is
hardcoded in Python, the mutation has no effect and the test fails —
meaning FY 2026-27 could not be added as a pure data change.
"""
from __future__ import annotations

from kara_tax_engine import TaxComputer


def _fresh_computer() -> TaxComputer:
    return TaxComputer(fy="2025-26")


def _allowed(result, section: str) -> int:
    entry = next(d for d in result.deductions_applied if d.section == section)
    return entry.allowed


def test_80c_combined_cap_comes_from_yaml():
    c = _fresh_computer()
    c.rules.load_deduction_rule("section_80c")["combined_cap"] = 100_000
    r = c.compute(gross_salary=1_500_000, regime="old", deductions={"80C": 150_000})
    assert _allowed(r, "80C/80CCC/80CCD(1)") == 100_000


def test_80ccd_1b_cap_comes_from_yaml():
    c = _fresh_computer()
    rule = c.rules.load_deduction_rule("section_80ccd")
    for sub in rule["sub_sections"]:
        if sub["section"] == "80CCD(1B)":
            sub["cap"] = 75_000
    r = c.compute(gross_salary=1_500_000, regime="old", deductions={"80CCD1B": 80_000})
    assert _allowed(r, "80CCD(1B)") == 75_000


def test_80d_self_cap_comes_from_yaml():
    c = _fresh_computer()
    c.rules.load_deduction_rule("section_80d")["limits"]["self_family"]["below_60"] = 30_000
    r = c.compute(gross_salary=1_500_000, regime="old", deductions={"80D": 40_000})
    assert _allowed(r, "80D") == 30_000


def test_80d_parents_caps_come_from_yaml():
    c = _fresh_computer()
    c.rules.load_deduction_rule("section_80d")["limits"]["parents"]["senior"] = 60_000
    r = c.compute(
        gross_salary=1_500_000,
        regime="old",
        deductions={"80D_parents": 70_000, "parents_senior": True},
    )
    assert _allowed(r, "80D") == 60_000


def test_80tta_cap_comes_from_yaml():
    c = _fresh_computer()
    c.rules.load_deduction_rule("section_80tta_80ttb")["section_80tta"]["cap"] = 12_000
    r = c.compute(gross_salary=1_000_000, regime="old", deductions={"80TTA": 15_000})
    assert _allowed(r, "80TTA") == 12_000


def test_80ttb_cap_comes_from_yaml():
    c = _fresh_computer()
    c.rules.load_deduction_rule("section_80tta_80ttb")["section_80ttb"]["cap"] = 60_000
    r = c.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80TTB": 70_000},
    )
    assert _allowed(r, "80TTB") == 60_000


def test_80u_limits_come_from_yaml():
    c = _fresh_computer()
    limits = c.rules.load_deduction_rule("section_80u_80dd")["section_80u"]["limits"]
    limits["normal_disability"] = 80_000
    r = c.compute(gross_salary=1_000_000, regime="old", deductions={"80U": 80_000})
    assert _allowed(r, "80U") == 80_000


def test_24b_cap_comes_from_yaml():
    c = _fresh_computer()
    c.rules.load_deduction_rule("section_24b")["limits"]["self_occupied"]["cap"] = 250_000
    r = c.compute(gross_salary=1_500_000, regime="old", deductions={"24b": 300_000})
    assert _allowed(r, "24(b)") == 250_000


def test_hra_percentages_come_from_yaml():
    c = _fresh_computer()
    hra_rule = c.rules.load_deduction_rule("hra")
    hra_rule["metro_percent"] = 0.60  # raise the metro limit
    r = c.compute(
        gross_salary=1_800_000,
        regime="old",
        hra_details={
            "hra_received": 500_000,
            "basic_salary": 720_000,
            "rent_paid": 600_000,
            "is_metro": True,
        },
    )
    # min(500000, 60% x 720000 = 432000, 600000 - 72000 = 528000) = 432000
    assert _allowed(r, "10(13A)") == 432_000
