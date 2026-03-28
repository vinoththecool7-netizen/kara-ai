"""Regime comparison engine — Old vs New regime analysis.

Computes tax under both regimes, recommends the optimal one,
calculates breakeven deductions, and provides deduction impact analysis.
"""

from __future__ import annotations

from kara_tax_engine.models import (
    Regime,
    RegimeComparison,
    TaxBreakdown,
    TaxProfile,
)

# Map deduction section names to the Deductions model fields that
# should be zeroed when measuring that section's impact.
_SECTION_FIELD_MAP: dict[str, list[str]] = {
    "80C/80CCC/80CCD(1)": [
        "section_80c",
        "section_80ccc",
        "section_80ccd_1",
    ],
    "80CCD(1B)": ["section_80ccd_1b"],
    "80CCD(2)": ["section_80ccd_2"],
    "80D": ["section_80d", "section_80d_parents"],
    "80E": ["section_80e"],
    "80G": ["section_80g"],
    "80TTA": ["section_80tta"],
    "80TTB": ["section_80ttb"],
    "80U": ["section_80u"],
    "80DD": ["section_80dd"],
    "24(b)": ["section_24b"],
}


class RegimeComparator:
    """Compare old and new tax regimes for a given profile."""

    def __init__(self, fy: str = "2025-26") -> None:
        from kara_tax_engine.computer import TaxComputer

        self.computer = TaxComputer(fy=fy)
        self.fy = fy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(self, profile: TaxProfile) -> RegimeComparison:
        """Compute tax under both regimes and return comparison."""
        # Compute under old regime
        old_profile = profile.model_copy(update={"regime": Regime.OLD})
        old_result = self.computer.compute_from_profile(old_profile)

        # Compute under new regime
        new_profile = profile.model_copy(update={"regime": Regime.NEW})
        new_result = self.computer.compute_from_profile(new_profile)

        # Determine recommendation
        if old_result.total_tax_payable <= new_result.total_tax_payable:
            recommended = Regime.OLD
            savings = new_result.total_tax_payable - old_result.total_tax_payable
        else:
            recommended = Regime.NEW
            savings = old_result.total_tax_payable - new_result.total_tax_payable

        # Breakeven analysis
        breakeven = self._compute_breakeven_deductions(
            profile,
            new_result.total_tax_payable,
        )

        # Deduction impact (only meaningful for old regime)
        deduction_impact = self._compute_deduction_impact(
            profile,
            old_result,
        )

        # Build explanation
        explanation = self._build_explanation(
            recommended,
            savings,
            old_result,
            new_result,
            breakeven,
            deduction_impact,
        )

        return RegimeComparison(
            old_regime=old_result,
            new_regime=new_result,
            recommended_regime=recommended,
            savings=savings,
            breakeven_deductions=breakeven,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Breakeven deductions via binary search
    # ------------------------------------------------------------------

    def _compute_breakeven_deductions(
        self,
        profile: TaxProfile,
        new_regime_tax: int,
    ) -> int:
        """Find the 80C deduction where old regime tax <= new regime tax.

        Binary-searches in [0, 150_000] with 1000 Rs steps.
        Returns 0 if old already wins or breakeven is unreachable.
        """
        # Check if old regime already wins at current deductions
        old_profile = profile.model_copy(
            update={"regime": Regime.OLD},
        )
        current_old = self.computer.compute_from_profile(old_profile)
        if current_old.total_tax_payable <= new_regime_tax:
            return 0

        # Check if max 80C can make old regime win
        max_old = self._old_tax_with_80c(profile, 150_000)
        if max_old > new_regime_tax:
            return 0  # Unreachable within 150K

        # Binary search for the minimum 80C that makes old <= new
        lo, hi = 0, 150_000
        while hi - lo > 1000:
            mid = ((lo + hi) // 2000) * 1000  # Snap to 1000 grid
            if mid == lo:
                mid = lo + 1000
            old_tax = self._old_tax_with_80c(profile, mid)
            if old_tax <= new_regime_tax:
                hi = mid
            else:
                lo = mid

        # Return hi (first value where old <= new), snapped to 1000
        return hi

    def _old_tax_with_80c(
        self,
        profile: TaxProfile,
        amount_80c: int,
    ) -> int:
        """Compute old-regime tax with a specific 80C deduction."""
        new_ded = profile.deductions.model_copy(
            update={"section_80c": amount_80c},
        )
        modified = profile.model_copy(
            update={"regime": Regime.OLD, "deductions": new_ded},
        )
        result = self.computer.compute_from_profile(modified)
        return result.total_tax_payable

    # ------------------------------------------------------------------
    # Deduction impact analysis
    # ------------------------------------------------------------------

    def _compute_deduction_impact(
        self,
        profile: TaxProfile,
        old_result: TaxBreakdown,
    ) -> dict[str, int]:
        """Measure each deduction's tax saving in old regime.

        For each applied deduction with allowed > 0, zeros it out
        and measures the tax increase.
        """
        impact: dict[str, int] = {}
        base_tax = old_result.total_tax_payable

        for ded_result in old_result.deductions_applied:
            if ded_result.allowed <= 0:
                continue
            section = ded_result.section

            # Skip HRA — cannot easily zero from profile
            if section == "10(13A)":
                continue

            fields = _SECTION_FIELD_MAP.get(section)
            if not fields:
                continue

            # Build zeroed-out deductions
            zero_updates: dict[str, int] = {f: 0 for f in fields}
            new_ded = profile.deductions.model_copy(
                update=zero_updates,
            )
            modified = profile.model_copy(
                update={"regime": Regime.OLD, "deductions": new_ded},
            )
            result = self.computer.compute_from_profile(modified)
            delta = result.total_tax_payable - base_tax
            if delta > 0:
                impact[section] = delta

        return impact

    # ------------------------------------------------------------------
    # Explanation builder
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        recommended: Regime,
        savings: int,
        old_result: TaxBreakdown,
        new_result: TaxBreakdown,
        breakeven: int,
        deduction_impact: dict[str, int],
    ) -> str:
        """Build a rich human-readable explanation string."""
        parts: list[str] = []

        # Recommendation and savings
        regime_name = "Old" if recommended == Regime.OLD else "New"
        parts.append(f"{regime_name} regime saves ₹{savings:,}")

        # Effective tax rate comparison
        parts.append(
            f"Effective rate: Old {old_result.effective_tax_rate}%"
            f" vs New {new_result.effective_tax_rate}%"
        )

        # Breakeven info
        if breakeven > 0:
            parts.append(
                f"You need ₹{breakeven:,} in Section 80C deductions for old regime to break even"
            )

        # Deduction savings (when old regime wins)
        if recommended == Regime.OLD and deduction_impact:
            total_saving = sum(deduction_impact.values())
            detail = ", ".join(f"{s}: ₹{v:,}" for s, v in deduction_impact.items())
            parts.append(f"Total deduction savings: ₹{total_saving:,} ({detail})")

        return ". ".join(parts)
