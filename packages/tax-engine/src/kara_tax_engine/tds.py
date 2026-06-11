"""TDS (Tax Deducted at Source) rate lookup — fully YAML-rule-driven.

Rates and thresholds live in ``rules/<fy>/tds/rates.yaml``; adding a new
financial year is a data change, not a code change.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from kara_tax_engine.loader import RuleSet


class TDSResult(BaseModel):
    """Outcome of a TDS rate lookup (and optional amount computation)."""

    payment_type: str
    section: str
    description: str
    rate: float | None  # None => not a flat rate (e.g. slab for salary)
    rate_description: str = ""
    threshold: int
    threshold_period: str = "annual"
    amount: int | None = None
    applicable: bool | None = None  # None when no amount was supplied
    tds_amount: int = 0
    note: str = ""


class TDSCalculator:
    """Look up TDS sections/rates and compute deduction amounts."""

    def __init__(self, fy: str = "2025-26") -> None:
        self.fy = fy
        self.rules = RuleSet(fy)
        data = self.rules._load("tds/rates.yaml")
        self._types: dict[str, dict[str, Any]] = data["payment_types"]
        self._aliases: dict[str, str] = data.get("aliases", {})
        self._no_pan_rate: float = data.get("no_pan_rate", 0.20)

    def payment_types(self) -> list[str]:
        """All canonical payment type keys."""
        return sorted(self._types)

    def lookup(
        self,
        payment_type: str,
        amount: int | None = None,
        *,
        has_pan: bool = True,
        is_senior: bool = False,
    ) -> TDSResult:
        """Resolve the TDS treatment for a payment.

        Args:
            payment_type: One of :meth:`payment_types` (or a known alias).
            amount: Optional payment amount; when given, applicability and the
                TDS amount are computed against the threshold.
            has_pan: False applies s.206AA — higher of the rate or 20%.
            is_senior: Uses the senior-citizen threshold where one exists
                (e.g. s.194A bank interest).
        """
        key = payment_type.strip().lower()
        key = self._aliases.get(key, key)
        if key not in self._types:
            known = ", ".join(sorted(list(self._types) + list(self._aliases)))
            raise ValueError(f"Unknown payment type '{payment_type}'. Known types: {known}")

        spec = self._types[key]
        rate: float | None = spec.get("rate")
        note_parts = [spec["note"]] if spec.get("note") else []

        threshold = spec["threshold"]
        if is_senior and spec.get("threshold_senior"):
            threshold = spec["threshold_senior"]

        # s.206AA — missing PAN raises the rate to at least 20%
        if not has_pan and rate is not None:
            if rate < self._no_pan_rate:
                rate = self._no_pan_rate
            note_parts.append(
                f"Higher rate ({self._no_pan_rate * 100:.0f}%) applied due to missing PAN (s.206AA)"
            )

        applicable: bool | None = None
        tds_amount = 0
        if amount is not None:
            applicable = amount > threshold
            if applicable and rate is not None:
                tds_amount = math.ceil(amount * rate)

        return TDSResult(
            payment_type=key,
            section=spec["section"],
            description=spec["description"],
            rate=rate,
            rate_description=spec.get("rate_description", ""),
            threshold=threshold,
            threshold_period=spec.get("threshold_period", "annual"),
            amount=amount,
            applicable=applicable,
            tds_amount=tds_amount,
            note="; ".join(note_parts),
        )
