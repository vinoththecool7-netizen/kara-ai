"""Tests for the advance tax scheduler and §234A/B/C interest (FY 2025-26)."""
from __future__ import annotations

from datetime import date

import pytest

from kara_tax_engine.advance_tax import AdvanceTaxCalculator
from kara_tax_engine.interest import (
    interest_234a,
    interest_234b,
    interest_234c,
)


@pytest.fixture(scope="module")
def calc():
    return AdvanceTaxCalculator(fy="2025-26")


# ---------------------------------------------------------------------------
# Advance tax schedule
# ---------------------------------------------------------------------------


class TestAdvanceTaxSchedule:
    def test_not_required_below_10k(self, calc):
        s = calc.schedule(total_estimated_tax=15_000, tds_deducted=6_000)
        assert s.required is False
        assert s.net_liability == 9_000
        assert s.installments == []

    def test_required_at_10k(self, calc):
        s = calc.schedule(total_estimated_tax=10_000)
        assert s.required is True

    def test_quarterly_schedule_amounts_and_dates(self, calc):
        s = calc.schedule(total_estimated_tax=100_000)
        assert [i.cumulative_pct for i in s.installments] == [15, 45, 75, 100]
        assert [i.cumulative_due for i in s.installments] == [15_000, 45_000, 75_000, 100_000]
        assert [i.amount_due for i in s.installments] == [15_000, 30_000, 30_000, 25_000]
        assert s.installments[0].due_date == date(2025, 6, 15)
        assert s.installments[1].due_date == date(2025, 9, 15)
        assert s.installments[2].due_date == date(2025, 12, 15)
        assert s.installments[3].due_date == date(2026, 3, 15)

    def test_tds_reduces_net_liability(self, calc):
        s = calc.schedule(total_estimated_tax=150_000, tds_deducted=50_000)
        assert s.net_liability == 100_000
        assert s.installments[-1].cumulative_due == 100_000

    def test_presumptive_single_installment(self, calc):
        """44AD/44ADA taxpayers pay 100% in one installment by 15 March."""
        s = calc.schedule(total_estimated_tax=100_000, is_presumptive=True)
        assert len(s.installments) == 1
        assert s.installments[0].cumulative_pct == 100
        assert s.installments[0].due_date == date(2026, 3, 15)

    def test_resident_senior_without_business_exempt(self, calc):
        """s.207(2): resident seniors with no business income owe no advance tax."""
        s = calc.schedule(
            total_estimated_tax=500_000,
            is_senior_without_business=True,
        )
        assert s.required is False
        assert "senior" in s.reason.lower()


# ---------------------------------------------------------------------------
# Section 234A — late filing
# ---------------------------------------------------------------------------


class Test234A:
    def test_no_interest_when_filed_on_time(self):
        r = interest_234a(
            unpaid_tax=100_000,
            due_date=date(2026, 7, 31),
            filing_date=date(2026, 7, 31),
        )
        assert r.interest == 0
        assert r.months == 0

    def test_part_month_counts_as_full(self):
        r = interest_234a(
            unpaid_tax=100_000,
            due_date=date(2026, 7, 31),
            filing_date=date(2026, 8, 1),
        )
        assert r.months == 1
        assert r.interest == 1_000  # 1% per month

    def test_three_months_late(self):
        r = interest_234a(
            unpaid_tax=100_000,
            due_date=date(2026, 7, 31),
            filing_date=date(2026, 10, 15),
        )
        assert r.months == 3
        assert r.interest == 3_000

    def test_base_rounded_down_to_hundred(self):
        """Rule 119A: the principal is rounded down to a multiple of ₹100."""
        r = interest_234a(
            unpaid_tax=99_949,
            due_date=date(2026, 7, 31),
            filing_date=date(2026, 8, 10),
        )
        assert r.interest == 999  # 1% of 99,900


# ---------------------------------------------------------------------------
# Section 234B — advance tax default
# ---------------------------------------------------------------------------


class Test234B:
    def test_not_applicable_when_90_percent_of_assessed_tax_paid(self):
        """The 90% test applies to assessed tax (total tax MINUS TDS)."""
        r = interest_234b(
            assessed_tax=200_000,
            tds_deducted=100_000,
            advance_tax_paid=90_000,
            until=date(2026, 7, 31),
            fy="2025-26",
        )
        assert r.interest == 0  # 90K = 90% of the 100K assessed tax

    def test_shortfall_charged_from_april(self):
        """Paid only 50%: 1%/month on the shortfall from 1 April."""
        r = interest_234b(
            assessed_tax=200_000,
            tds_deducted=0,
            advance_tax_paid=100_000,
            until=date(2026, 7, 31),
            fy="2025-26",
        )
        assert r.months == 4  # Apr, May, Jun, part of Jul
        assert r.interest == 4_000  # 1% x 4 on 100,000

    def test_nothing_paid(self):
        r = interest_234b(
            assessed_tax=100_000,
            tds_deducted=0,
            advance_tax_paid=0,
            until=date(2026, 4, 30),
            fy="2025-26",
        )
        assert r.months == 1
        assert r.interest == 1_000


# ---------------------------------------------------------------------------
# Section 234C — deferment of advance tax
# ---------------------------------------------------------------------------


class Test234C:
    def test_nothing_paid_all_quarters(self):
        """Q1-Q3 shortfalls bear 3 months interest; Q4 bears 1 month.

        Tax 100,000: 15,000x3% + 45,000x3% + 75,000x3% + 100,000x1% = 5,050.
        """
        r = interest_234c(
            total_tax_liability=100_000,
            tds_deducted=0,
            cumulative_paid={"q1": 0, "q2": 0, "q3": 0, "q4": 0},
            fy="2025-26",
        )
        assert r.interest == 450 + 1_350 + 2_250 + 1_000

    def test_q1_tolerance_12_percent(self):
        """No Q1 interest if at least 12% (vs 15%) was paid by 15 June."""
        r = interest_234c(
            total_tax_liability=100_000,
            tds_deducted=0,
            cumulative_paid={"q1": 12_000, "q2": 45_000, "q3": 75_000, "q4": 100_000},
            fy="2025-26",
        )
        assert r.interest == 0

    def test_q2_tolerance_36_percent(self):
        r = interest_234c(
            total_tax_liability=100_000,
            tds_deducted=0,
            cumulative_paid={"q1": 15_000, "q2": 36_000, "q3": 75_000, "q4": 100_000},
            fy="2025-26",
        )
        assert r.interest == 0

    def test_tds_counts_toward_installments(self):
        """TDS reduces the liability the installments are computed on."""
        r = interest_234c(
            total_tax_liability=100_000,
            tds_deducted=100_000,
            cumulative_paid={"q1": 0, "q2": 0, "q3": 0, "q4": 0},
            fy="2025-26",
        )
        assert r.interest == 0

    def test_presumptive_only_q4(self):
        """44AD/ADA: only the 15 March installment matters; 1 month interest."""
        r = interest_234c(
            total_tax_liability=100_000,
            tds_deducted=0,
            cumulative_paid={"q4": 0},
            fy="2025-26",
            is_presumptive=True,
        )
        assert r.interest == 1_000
