"""Tests for Section 80D health insurance and HRA exemption (FY 2025-26).

Section 80D — Health insurance premium deduction (old regime only):
  Self/family cap: ₹25,000 (below_60) or ₹50,000 (senior/super_senior).
  Parents cap: ₹25,000, or ₹50,000 when parents_senior=True is declared.
  Combined into a single DeductionResult entry with section="80D".

HRA exemption — Section 10(13A) (old regime only):
  Exemption = min(HRA received, metro_pct * basic, max(0, rent - 10% * basic)).
  metro_pct = 50% for metro, 40% for non-metro.
  Returns 0 if hra_received <= 0 or rent_paid <= 0.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Group A: 80D Self/Family Below-60 (5 tests)
# ---------------------------------------------------------------------------


def test_80d_self_25k_below60(computer):
    """Below-60, 80D=25000 — allowed equals full 25K cap."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80D": 25_000})
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 25_000


def test_80d_self_exceeds_cap_below60(computer):
    """Below-60, 80D=40000 — capped at 25K for self."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80D": 40_000})
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 25_000


def test_80d_self_partial_claim(computer):
    """Below-60, 80D=15000 — allowed equals claimed (under cap)."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80D": 15_000})
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 15_000


def test_80d_zero_claim(computer):
    """80D=0, no parents — no 80D entry in deductions_applied."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80D": 0})
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is None


def test_80d_self_1_rupee(computer):
    """Below-60, 80D=1 — even minimal claim is allowed."""
    r = computer.compute(gross_salary=1_000_000, regime="old", deductions={"80D": 1})
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 1


# ---------------------------------------------------------------------------
# Group B: 80D Senior Citizen (4 tests)
# ---------------------------------------------------------------------------


def test_80d_self_50k_senior(computer):
    """Senior, 80D=50000 — senior self cap is 50K, full amount allowed."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80D": 50_000},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 50_000


def test_80d_self_exceeds_50k_senior(computer):
    """Senior, 80D=60000 — capped at 50K."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80D": 60_000},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 50_000


def test_80d_self_30k_senior(computer):
    """Senior, 80D=30000 — under cap, full amount allowed."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="senior",
        deductions={"80D": 30_000},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 30_000


def test_80d_self_50k_super_senior(computer):
    """Super-senior, 80D=50000 — same 50K senior cap applies."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        age_category="super_senior",
        deductions={"80D": 50_000},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 50_000


# ---------------------------------------------------------------------------
# Group C: 80D Parents (4 tests)
# ---------------------------------------------------------------------------


def test_80d_parents_below60_capped_25k(computer):
    """Parents below 60 (default), 80D_parents=50000 — capped at ₹25K.

    Without an explicit parents_senior declaration the engine must use the
    conservative ₹25,000 cap, never over-allowing the deduction.
    """
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80D_parents": 50_000},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.claimed == 50_000
    assert entry.allowed == 25_000


def test_80d_parents_senior_50k(computer):
    """Senior parents declared, 80D_parents=50000 — allowed=50000."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80D_parents": 50_000, "parents_senior": True},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.claimed == 50_000
    assert entry.allowed == 50_000


def test_80d_parents_senior_exceeds_cap(computer):
    """Senior parents, 80D_parents=60000 — capped at 50K."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80D_parents": 60_000, "parents_senior": True},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.allowed == 50_000


def test_80d_self_plus_parents_below60(computer):
    """Below-60, self=25K + parents=25K — claimed=50K, allowed=50K."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80D": 25_000, "80D_parents": 25_000},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.claimed == 50_000
    assert entry.allowed == 50_000
    assert r.total_deductions == 50_000


def test_80d_self_below60_parents_senior(computer):
    """Below-60, self=25K + senior parents=50K — claimed=75K, allowed=75K."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        deductions={"80D": 25_000, "80D_parents": 50_000, "parents_senior": True},
    )
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is not None
    assert entry.claimed == 75_000
    assert entry.allowed == 75_000
    assert r.total_deductions == 75_000


# ---------------------------------------------------------------------------
# Group D: 80D Regime Filtering (2 tests)
# ---------------------------------------------------------------------------


def test_80d_rejected_in_new_regime(computer):
    """New regime, 80D=25000 — rejected, total_deductions=0."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="new",
        deductions={"80D": 25_000},
    )
    assert r.total_deductions == 0
    entry = next((d for d in r.deductions_applied if d.section == "80D"), None)
    assert entry is None


def test_80d_parents_rejected_in_new_regime(computer):
    """New regime, 80D_parents=50000 — rejected, total_deductions=0."""
    r = computer.compute(
        gross_salary=1_000_000,
        regime="new",
        deductions={"80D_parents": 50_000},
    )
    assert r.total_deductions == 0


# ---------------------------------------------------------------------------
# Group E: HRA Metro (5 tests)
# ---------------------------------------------------------------------------


def test_hra_metro_basic_case(computer):
    """Metro HRA: option3 (rent-10%basic) is limiting.

    Option1=240000, Option2=floor(600000*0.5)=300000,
    Option3=max(0, 180000-floor(600000*0.1))=120000. Min=120000.
    """
    r = computer.compute(
        gross_salary=1_040_000,
        regime="old",
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 180_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 120_000


def test_hra_metro_hra_is_limiting(computer):
    """Metro HRA: HRA received is the limiting factor.

    Option1=100000, Option2=300000, Option3=300000-60000=240000. Min=100000.
    """
    r = computer.compute(
        gross_salary=1_000_000,
        regime="old",
        hra_details={
            "hra_received": 100_000,
            "basic_salary": 600_000,
            "rent_paid": 300_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 100_000


def test_hra_metro_basic_pct_is_limiting(computer):
    """Metro HRA: 50% of basic is the limiting factor.

    Option1=300000, Option2=floor(200000*0.5)=100000,
    Option3=300000-20000=280000. Min=100000.
    """
    r = computer.compute(
        gross_salary=800_000,
        regime="old",
        hra_details={
            "hra_received": 300_000,
            "basic_salary": 200_000,
            "rent_paid": 300_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 100_000


def test_hra_metro_rent_minus_10pct_limiting(computer):
    """Metro HRA: rent-10%basic limiting (same scenario as basic case).

    Option1=240000, Option2=300000, Option3=180000-60000=120000. Min=120000.
    """
    r = computer.compute(
        gross_salary=1_040_000,
        regime="old",
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 180_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 120_000


def test_hra_metro_high_rent(computer):
    """Metro HRA: 50% of basic is limiting with high rent.

    Option1=400000, Option2=floor(600000*0.5)=300000,
    Option3=500000-60000=440000. Min=300000.
    """
    r = computer.compute(
        gross_salary=1_500_000,
        regime="old",
        hra_details={
            "hra_received": 400_000,
            "basic_salary": 600_000,
            "rent_paid": 500_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 300_000


# ---------------------------------------------------------------------------
# Group F: HRA Non-Metro + Edge Cases (5 tests)
# ---------------------------------------------------------------------------


def test_hra_non_metro_40pct(computer):
    """Non-metro HRA: option3 is limiting.

    Option1=240000, Option2=floor(600000*0.4)=240000,
    Option3=180000-60000=120000. Min=120000.
    """
    r = computer.compute(
        gross_salary=1_040_000,
        regime="old",
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 180_000,
            "is_metro": False,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 120_000


def test_hra_non_metro_basic_pct_lower(computer):
    """Non-metro HRA: 40% of basic ties with option3.

    Option1=200000, Option2=floor(400000*0.4)=160000,
    Option3=200000-40000=160000. Min=160000.
    """
    r = computer.compute(
        gross_salary=800_000,
        regime="old",
        hra_details={
            "hra_received": 200_000,
            "basic_salary": 400_000,
            "rent_paid": 200_000,
            "is_metro": False,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is not None
    assert entry.allowed == 160_000


def test_hra_zero_rent(computer):
    """HRA with rent=0 — exemption is 0 (code returns 0 when rent<=0)."""
    r = computer.compute(
        gross_salary=1_040_000,
        regime="old",
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 0,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is None


def test_hra_rent_below_10pct_basic(computer):
    """HRA where rent < 10% of basic — option3 becomes 0.

    Option1=240000, Option2=300000, Option3=max(0, 50000-60000)=0. Min=0.
    """
    r = computer.compute(
        gross_salary=1_040_000,
        regime="old",
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 50_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    # When exemption is 0, the code doesn't add an entry (hra_exempt > 0 check)
    assert entry is None


def test_hra_rejected_in_new_regime(computer):
    """New regime with HRA details — no exemption allowed."""
    r = computer.compute(
        gross_salary=1_040_000,
        regime="new",
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 180_000,
            "is_metro": True,
        },
    )
    entry = next((d for d in r.deductions_applied if d.section == "10(13A)"), None)
    assert entry is None
    assert r.total_deductions == 0


# ---------------------------------------------------------------------------
# Group G: Combined Deductions (3 tests)
# ---------------------------------------------------------------------------


def test_hra_plus_80c_combined(computer):
    """HRA exemption + 80C combined deductions.

    HRA: min(240000, 300000, 120000) = 120000.
    80C: 150000. Total deductions: 270000.
    Taxable: (1500000 - 50000) - 270000 = 1180000.
    """
    r = computer.compute(
        gross_salary=1_500_000,
        regime="old",
        deductions={"80C": 150_000},
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 180_000,
            "is_metro": True,
        },
    )
    assert r.total_deductions == 270_000
    assert r.taxable_income == 1_180_000


def test_hra_plus_80c_plus_80d_stacked(computer):
    """HRA + 80C + 80D all stacked.

    HRA: 120000. 80C: 150000. 80D: 25000. Total: 295000.
    Taxable: (2000000 - 50000) - 295000 = 1655000.
    """
    r = computer.compute(
        gross_salary=2_000_000,
        regime="old",
        deductions={"80C": 150_000, "80D": 25_000},
        hra_details={
            "hra_received": 240_000,
            "basic_salary": 600_000,
            "rent_paid": 180_000,
            "is_metro": True,
        },
    )
    assert r.total_deductions == 295_000
    assert r.taxable_income == 1_655_000


def test_deductions_cannot_reduce_taxable_below_zero(computer):
    """Taxable income should never go below zero even with large deductions.

    Gross=300000, std_ded=50000, GTI=250000, 80C=150000.
    Taxable = max(0, 250000-150000) = 100000.
    """
    r = computer.compute(
        gross_salary=300_000,
        regime="old",
        deductions={"80C": 150_000},
    )
    assert r.taxable_income >= 0
    assert r.taxable_income == 100_000
