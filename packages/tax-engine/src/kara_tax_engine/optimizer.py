"""Deduction optimizer — find tax-saving opportunities.

Analyzes current deductions and suggests optimal investments.
"""

from __future__ import annotations

import re

from kara_tax_engine.models import (
    AgeCategory,
    Deductions,
    OptimizationResult,
    OptimizationSuggestion,
    Regime,
    TaxProfile,
)


class DeductionOptimizer:
    """Find deduction gaps and suggest tax-saving investments."""

    def __init__(self, fy: str = "2025-26") -> None:
        from kara_tax_engine.computer import TaxComputer

        self.fy = fy
        self.computer = TaxComputer(fy=fy)

    def optimize(self, profile: TaxProfile) -> OptimizationResult:
        """Analyze deductions and suggest optimizations.

        Always optimizes for old regime. The comparator handles regime
        recommendation separately.
        """
        ded = profile.deductions

        # Step 1: Compute current tax under old regime
        old_profile = profile.model_copy(update={"regime": Regime.OLD})
        current_result = self.computer.compute_from_profile(old_profile)
        current_tax = current_result.total_tax_payable

        # Step 2: Compute deduction usage vs caps
        # 80C/80CCC/80CCD(1): combined cap 1,50,000
        combined_80c = ded.section_80c + ded.section_80ccc + ded.section_80ccd_1
        used_80c = min(combined_80c, 150_000)
        remaining_80c = 150_000 - used_80c

        # 80CCD(1B): cap 50,000
        used_80ccd_1b = min(ded.section_80ccd_1b, 50_000)
        remaining_80ccd_1b = 50_000 - used_80ccd_1b

        # 80D: self cap depends on age, parents cap = 50K
        self_cap = 50_000 if profile.age_category != AgeCategory.BELOW_60 else 25_000
        parents_cap = 50_000
        used_80d = min(ded.section_80d, self_cap) + min(ded.section_80d_parents, parents_cap)
        total_80d_cap = self_cap + parents_cap
        remaining_80d = total_80d_cap - used_80d

        # Early return if no tax liability
        if current_tax == 0:
            return OptimizationResult(
                current_tax=0,
                optimized_tax=0,
                total_potential_saving=0,
                suggestions=[],
                section_80c_used=used_80c,
                section_80c_remaining=remaining_80c,
                section_80d_used=used_80d,
                section_80d_remaining=remaining_80d,
                section_80ccd_1b_used=used_80ccd_1b,
                section_80ccd_1b_remaining=remaining_80ccd_1b,
            )

        # Step 3: Generate suggestions for each gap
        suggestions: list[OptimizationSuggestion] = []

        # 80C gap
        if remaining_80c > 0:
            saving_80c = self._compute_suggestion_saving(
                old_profile, current_tax, "80C", remaining_80c
            )
            suggestions.append(
                OptimizationSuggestion(
                    section="80C",
                    instrument="ELSS",
                    suggested_amount=remaining_80c,
                    potential_tax_saving=saving_80c,
                    lock_in_years=3,
                    expected_return_range=[12.0, 15.0],
                    note="Best returns, shortest lock-in among 80C options",
                )
            )
            suggestions.append(
                OptimizationSuggestion(
                    section="80C",
                    instrument="PPF",
                    suggested_amount=remaining_80c,
                    potential_tax_saving=saving_80c,
                    lock_in_years=15,
                    expected_return_range=[7.1],
                    note="Government-backed, tax-free returns",
                )
            )
            suggestions.append(
                OptimizationSuggestion(
                    section="80C",
                    instrument="5-Year Tax Saving FD",
                    suggested_amount=remaining_80c,
                    potential_tax_saving=saving_80c,
                    lock_in_years=5,
                    expected_return_range=[7.0],
                    note=("Guaranteed returns, suitable for risk-averse investors"),
                )
            )

        # 80CCD(1B) gap
        if remaining_80ccd_1b > 0:
            saving_nps = self._compute_suggestion_saving(
                old_profile, current_tax, "80CCD(1B)", remaining_80ccd_1b
            )
            suggestions.append(
                OptimizationSuggestion(
                    section="80CCD(1B)",
                    instrument="NPS",
                    suggested_amount=remaining_80ccd_1b,
                    potential_tax_saving=saving_nps,
                    lock_in_years=None,
                    expected_return_range=[9.0, 12.0],
                    note=("Additional \u20b950,000 deduction over 80C limit"),
                )
            )

        # 80D gap
        if remaining_80d > 0:
            saving_80d = self._compute_suggestion_saving(
                old_profile, current_tax, "80D", remaining_80d
            )
            suggestions.append(
                OptimizationSuggestion(
                    section="80D",
                    instrument="Health Insurance",
                    suggested_amount=remaining_80d,
                    potential_tax_saving=saving_80d,
                    lock_in_years=None,
                    expected_return_range=[],
                    note=("Protects against medical expenses; mandatory for financial planning"),
                )
            )

        # Step 5: Sort by potential_tax_saving descending
        suggestions.sort(key=lambda s: s.potential_tax_saving, reverse=True)

        # Step 6: Compute optimized_tax — apply all unique section
        # deductions simultaneously (max suggestion per section)
        best_per_section: dict[str, int] = {}
        for s in suggestions:
            if s.section not in best_per_section:
                best_per_section[s.section] = s.suggested_amount
            else:
                best_per_section[s.section] = max(best_per_section[s.section], s.suggested_amount)

        if best_per_section:
            ded_dict = old_profile.deductions.model_dump()
            field_map = {
                "80C": "section_80c",
                "80CCD(1B)": "section_80ccd_1b",
                "80D": "section_80d",
            }
            for section, amount in best_per_section.items():
                field = field_map.get(section)
                if field:
                    ded_dict[field] = ded_dict.get(field, 0) + amount
            new_ded = Deductions(**ded_dict)
            optimized_profile = old_profile.model_copy(update={"deductions": new_ded})
            optimized_result = self.computer.compute_from_profile(optimized_profile)
            optimized_tax = optimized_result.total_tax_payable
        else:
            optimized_tax = current_tax

        total_potential_saving = max(0, current_tax - optimized_tax)

        return OptimizationResult(
            current_tax=current_tax,
            optimized_tax=optimized_tax,
            total_potential_saving=total_potential_saving,
            suggestions=suggestions,
            section_80c_used=used_80c,
            section_80c_remaining=remaining_80c,
            section_80d_used=used_80d,
            section_80d_remaining=remaining_80d,
            section_80ccd_1b_used=used_80ccd_1b,
            section_80ccd_1b_remaining=remaining_80ccd_1b,
        )

    def _compute_suggestion_saving(
        self,
        profile: TaxProfile,
        current_tax: int,
        section: str,
        amount: int,
    ) -> int:
        """Compute tax saving for a single additional deduction."""
        ded_dict = profile.deductions.model_dump()
        field_map = {
            "80C": "section_80c",
            "80CCD(1B)": "section_80ccd_1b",
            "80D": "section_80d",
        }
        field = field_map.get(section)
        if not field:
            return 0
        ded_dict[field] = ded_dict.get(field, 0) + amount
        new_ded = Deductions(**ded_dict)
        new_profile = profile.model_copy(update={"regime": Regime.OLD, "deductions": new_ded})
        new_result = self.computer.compute_from_profile(new_profile)
        return max(0, current_tax - new_result.total_tax_payable)

    def _parse_return_range(self, value: str) -> list[float]:
        """Parse YAML returns_indicative string to list of floats.

        Examples:
            "12-15%" -> [12.0, 15.0]
            "7.1%"  -> [7.1]
            "varies" -> []
        """
        if not value or value.lower() == "varies":
            return []
        cleaned = value.replace("%", "").strip()
        match = re.match(r"^([\d.]+)-([\d.]+)$", cleaned)
        if match:
            return [float(match.group(1)), float(match.group(2))]
        try:
            return [float(cleaned)]
        except ValueError:
            return []
