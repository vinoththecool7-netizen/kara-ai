"""Interest under sections 234A, 234B, and 234C.

All three charge simple interest at 1% per month or part thereof; the
principal is rounded down to a multiple of ₹100 (rule 119A).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

_RATE_PER_MONTH = 0.01


class InterestResult(BaseModel):
    section: str
    interest: int
    months: int = 0
    base_amount: int = 0
    explanation: str = ""


def _round_down_100(amount: int) -> int:
    """Rule 119A: round the principal down to a multiple of ₹100."""
    return max(0, amount // 100 * 100)


def _months_between(start_after: date, end: date) -> int:
    """Number of months (part = full) in the period starting the day after
    ``start_after`` and ending at ``end`` inclusive."""
    if end <= start_after:
        return 0
    months = (end.year - start_after.year) * 12 + (end.month - start_after.month)
    if end.day > start_after.day:
        months += 1
    return max(0, months)


# ---------------------------------------------------------------------------
# 234A — late filing
# ---------------------------------------------------------------------------


def interest_234a(unpaid_tax: int, due_date: date, filing_date: date) -> InterestResult:
    """Interest for filing the return after the due date.

    1% per month (or part) on the unpaid tax from the day after the due
    date until the actual filing date.
    """
    base = _round_down_100(unpaid_tax)
    months = _months_between(due_date, filing_date)
    interest = int(base * _RATE_PER_MONTH * months)
    return InterestResult(
        section="234A",
        interest=interest,
        months=months,
        base_amount=base,
        explanation=(
            f"Filed {months} month(s) after the due date: 1% x {months} on ₹{base:,}"
            if months
            else "Filed on or before the due date — no 234A interest"
        ),
    )


# ---------------------------------------------------------------------------
# 234B — default in payment of advance tax
# ---------------------------------------------------------------------------


def interest_234b(
    assessed_tax: int,
    tds_deducted: int,
    advance_tax_paid: int,
    until: date,
    fy: str,
) -> InterestResult:
    """Interest when advance tax paid is less than 90% of the liability.

    1% per month (or part) on the shortfall from 1 April following the FY
    until ``until`` (typically the filing/assessment date).
    """
    net_liability = assessed_tax - tds_deducted
    paid = advance_tax_paid
    if net_liability <= 0 or paid >= 0.9 * net_liability:
        return InterestResult(
            section="234B",
            interest=0,
            explanation="At least 90% of the assessed liability was paid — no 234B interest",
        )

    shortfall = _round_down_100(net_liability - paid)
    start_year = int(fy.split("-")[0])
    # Interest runs FROM 1 April (part of April = one full month);
    # _months_between starts the day AFTER its first argument, so anchoring
    # on 31 March makes April the first month.
    months = _months_between(date(start_year + 1, 3, 31), until)
    interest = int(shortfall * _RATE_PER_MONTH * months)
    return InterestResult(
        section="234B",
        interest=interest,
        months=months,
        base_amount=shortfall,
        explanation=(
            f"Advance tax below 90% of liability: 1% x {months} month(s) on ₹{shortfall:,}"
        ),
    )


# ---------------------------------------------------------------------------
# 234C — deferment of advance tax installments
# ---------------------------------------------------------------------------

# (quarter, cumulative %, tolerance %, months of interest)
_234C_SCHEDULE = [
    ("q1", 15, 12, 3),
    ("q2", 45, 36, 3),
    ("q3", 75, 75, 3),
    ("q4", 100, 100, 1),
]


def interest_234c(
    total_tax_liability: int,
    tds_deducted: int,
    cumulative_paid: dict[str, int],
    fy: str,  # noqa: ARG001 — kept for future FY-specific schedules
    *,
    is_presumptive: bool = False,
) -> InterestResult:
    """Interest for deferring advance tax installments.

    ``cumulative_paid`` maps quarter keys (q1..q4) to the cumulative advance
    tax paid by that installment's due date. Q1/Q2 carry a tolerance: no
    interest if at least 12%/36% was paid. Presumptive taxpayers are only
    assessed on the Q4 (15 March) installment.
    """
    net_liability = max(0, total_tax_liability - tds_deducted)
    if net_liability < 10_000:
        return InterestResult(
            section="234C",
            interest=0,
            explanation="Net liability below ₹10,000 — no advance tax obligation",
        )

    schedule = [q for q in _234C_SCHEDULE if q[0] == "q4"] if is_presumptive else _234C_SCHEDULE

    total_interest = 0
    parts: list[str] = []
    for quarter, pct, tolerance_pct, months in schedule:
        paid = cumulative_paid.get(quarter, 0)
        if paid >= net_liability * tolerance_pct / 100:
            continue
        due = net_liability * pct // 100
        shortfall = _round_down_100(due - paid)
        if shortfall <= 0:
            continue
        q_interest = int(shortfall * _RATE_PER_MONTH * months)
        total_interest += q_interest
        parts.append(f"{quarter.upper()}: 1% x {months} on ₹{shortfall:,} = ₹{q_interest:,}")

    return InterestResult(
        section="234C",
        interest=total_interest,
        base_amount=net_liability,
        explanation="; ".join(parts) if parts else "All installments met — no 234C interest",
    )
