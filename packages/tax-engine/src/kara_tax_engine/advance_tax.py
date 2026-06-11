"""Advance tax installment scheduler (s.208/211, FY-aware)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

# s.208 — advance tax applies when net liability reaches this amount
_MIN_LIABILITY = 10_000

# s.211 cumulative installment percentages and due dates (month, day).
# Q1-Q3 fall inside the financial year; Q4 is 15 March of the next
# calendar year (still inside the FY).
_INSTALLMENTS = [
    ("Q1", 15, (6, 15)),
    ("Q2", 45, (9, 15)),
    ("Q3", 75, (12, 15)),
    ("Q4", 100, (3, 15)),
]


class AdvanceTaxInstallment(BaseModel):
    quarter: str
    due_date: date
    cumulative_pct: int
    cumulative_due: int
    amount_due: int


class AdvanceTaxSchedule(BaseModel):
    required: bool
    reason: str = ""
    total_estimated_tax: int
    tds_deducted: int
    net_liability: int
    is_presumptive: bool = False
    installments: list[AdvanceTaxInstallment] = []


class AdvanceTaxCalculator:
    """Compute the advance tax installment schedule for a financial year."""

    def __init__(self, fy: str = "2025-26") -> None:
        self.fy = fy
        self._start_year = int(fy.split("-")[0])

    def _due_date(self, month: int, day: int) -> date:
        # March belongs to the next calendar year within the same FY
        year = self._start_year + 1 if month < 4 else self._start_year
        return date(year, month, day)

    def schedule(
        self,
        total_estimated_tax: int,
        tds_deducted: int = 0,
        *,
        is_presumptive: bool = False,
        is_senior_without_business: bool = False,
    ) -> AdvanceTaxSchedule:
        """Build the installment schedule.

        Args:
            total_estimated_tax: Estimated tax liability for the FY (₹).
            tds_deducted: TDS/TCS already deducted at source (₹).
            is_presumptive: 44AD/44ADA taxpayers pay 100% by 15 March.
            is_senior_without_business: Resident seniors (60+) with no
                business/professional income are exempt — s.207(2).
        """
        net = max(0, total_estimated_tax - tds_deducted)

        base = AdvanceTaxSchedule(
            required=False,
            total_estimated_tax=total_estimated_tax,
            tds_deducted=tds_deducted,
            net_liability=net,
            is_presumptive=is_presumptive,
        )

        if is_senior_without_business:
            base.reason = (
                "Not required: resident senior citizens without business or "
                "professional income are exempt from advance tax (s.207(2))"
            )
            return base

        if net < _MIN_LIABILITY:
            base.reason = (
                f"Not required: net tax liability (₹{net:,}) is below the "
                f"₹{_MIN_LIABILITY:,} threshold (s.208)"
            )
            return base

        base.required = True
        base.reason = "Advance tax payable in installments under s.211"

        if is_presumptive:
            month, day = _INSTALLMENTS[-1][2]
            base.installments = [
                AdvanceTaxInstallment(
                    quarter="Q4",
                    due_date=self._due_date(month, day),
                    cumulative_pct=100,
                    cumulative_due=net,
                    amount_due=net,
                )
            ]
            return base

        installments: list[AdvanceTaxInstallment] = []
        prev_due = 0
        for quarter, pct, (month, day) in _INSTALLMENTS:
            cumulative_due = net * pct // 100
            installments.append(
                AdvanceTaxInstallment(
                    quarter=quarter,
                    due_date=self._due_date(month, day),
                    cumulative_pct=pct,
                    cumulative_due=cumulative_due,
                    amount_due=cumulative_due - prev_due,
                )
            )
            prev_due = cumulative_due
        base.installments = installments
        return base
