"""Core tax computation engine — the heart of Kara.

Implements the deterministic 8-step Indian income tax computation pipeline:
  1. Aggregate income
  2. Apply deductions (regime-dependent)
  3. Compute tax on slabs
  4. Add capital gains tax (special rates)
  5. Compute surcharge
  6. Compute cess
  7. Apply Section 87A rebate (with marginal relief)
  8. Net tax payable
"""

from __future__ import annotations

import math
from typing import Any

from kara_tax_engine.loader import RuleSet
from kara_tax_engine.models import (
    AgeCategory,
    DeductionResult,
    Deductions,
    HRADetails,
    Regime,
    SlabBreakdown,
    TaxBreakdown,
    TaxProfile,
)


def _fmt(amount: int) -> str:
    """Format amount in Indian numbering: ₹12,50,000."""
    if amount < 0:
        return f"-₹{_fmt(-amount)[1:]}"
    s = str(amount)
    if len(s) <= 3:
        return f"₹{s}"
    last_three = s[-3:]
    remaining = s[:-3]
    groups = []
    while remaining:
        groups.append(remaining[-2:])
        remaining = remaining[:-2]
    groups.reverse()
    return f"₹{','.join(groups)},{last_three}"


class TaxComputer:
    """Deterministic Indian income tax calculator.

    Usage:
        computer = TaxComputer(fy="2025-26")
        result = computer.compute(gross_salary=1_500_000, regime="new")
        print(result.total_tax_payable)
    """

    def __init__(self, fy: str = "2025-26") -> None:
        self.rules = RuleSet(fy)
        self.fy = fy

    def compute(
        self,
        gross_salary: int = 0,
        regime: str = "new",
        age_category: str = "below_60",
        deductions: dict[str, int] | None = None,
        hra_details: dict[str, Any] | None = None,
        business_income: int = 0,
        house_property_income: int = 0,
        other_income: int = 0,
    ) -> TaxBreakdown:
        """Compute tax with a simple interface.

        Args:
            gross_salary: Total salary income.
            regime: "old" or "new".
            age_category: "below_60", "senior", or "super_senior".
            deductions: Dict of section -> amount, e.g. {"80C": 150000, "80D": 25000}.
            hra_details: Dict with keys: hra_received, basic_salary, rent_paid, is_metro.
            business_income: Income from business/profession.
            house_property_income: Income from house property (can be negative).
            other_income: Interest, dividends, etc.
        """
        regime_enum = Regime(regime)
        age_enum = AgeCategory(age_category)

        # Build deductions model
        ded = Deductions()
        if deductions:
            mapping = {
                "80C": "section_80c",
                "80c": "section_80c",
                "section_80c": "section_80c",
                "80CCC": "section_80ccc",
                "80CCD1": "section_80ccd_1",
                "80CCD1B": "section_80ccd_1b",
                "80CCD(1B)": "section_80ccd_1b",
                "80ccd_1b": "section_80ccd_1b",
                "section_80ccd_1b": "section_80ccd_1b",
                "80CCD2": "section_80ccd_2",
                "80CCD(2)": "section_80ccd_2",
                "section_80ccd_2": "section_80ccd_2",
                "80D": "section_80d",
                "80d": "section_80d",
                "section_80d": "section_80d",
                "80D_parents": "section_80d_parents",
                "section_80d_parents": "section_80d_parents",
                "80E": "section_80e",
                "section_80e": "section_80e",
                "80G": "section_80g",
                "section_80g": "section_80g",
                "80TTA": "section_80tta",
                "section_80tta": "section_80tta",
                "80TTB": "section_80ttb",
                "section_80ttb": "section_80ttb",
                "80U": "section_80u",
                "section_80u": "section_80u",
                "80DD": "section_80dd",
                "section_80dd": "section_80dd",
                "24b": "section_24b",
                "section_24b": "section_24b",
            }
            for key, value in deductions.items():
                if key == "parents_senior":
                    ded.parents_senior = bool(value)
                    continue
                attr = mapping.get(key)
                if attr and hasattr(ded, attr):
                    setattr(ded, attr, value)

        hra = None
        if hra_details:
            hra = HRADetails(**hra_details)

        profile = TaxProfile(
            financial_year=self.fy,
            regime=regime_enum,
            age_category=age_enum,
            gross_salary=gross_salary,
            deductions=ded,
            hra_details=hra,
            business_income=business_income,
            house_property_income=house_property_income,
            other_income=other_income,
        )

        return self.compute_from_profile(profile)

    def compute_from_profile(self, profile: TaxProfile) -> TaxBreakdown:
        """Full 8-step computation from a TaxProfile."""
        result = TaxBreakdown(
            regime=profile.regime,
            financial_year=profile.financial_year,
            assessment_year=profile.assessment_year,
            age_category=profile.age_category,
        )

        regime = profile.regime.value
        age = profile.age_category.value

        # --- Step 1: Aggregate Income ---
        gross_salary = profile.get_gross_salary()
        std_ded = self.rules.get_standard_deduction(regime) if gross_salary > 0 else 0
        net_salary = max(0, gross_salary - std_ded)

        result.gross_salary = gross_salary
        result.standard_deduction = std_ded
        result.net_salary = net_salary
        result.house_property_income = profile.house_property_income
        result.business_income = profile.business_income
        result.other_income = profile.other_income

        result.add_step(f"Gross salary: {_fmt(gross_salary)}")
        if std_ded > 0:
            result.add_step(f"Less: Standard deduction: {_fmt(std_ded)}")
            result.add_step(f"Net salary: {_fmt(net_salary)}")

        gti = net_salary + profile.business_income + profile.other_income
        # House property income can be negative (loss); set-off against
        # other heads is capped at ₹2L.
        hp_income = profile.house_property_income
        if hp_income < 0:
            hp_setoff = max(hp_income, -200000)  # Loss set-off capped at ₹2L
            gti += hp_setoff
            if hp_income < -200000:
                result.add_step(
                    f"House property loss: {_fmt(hp_income)}, "
                    f"set-off capped at {_fmt(-200000)}, carry forward: {_fmt(hp_income + 200000)}"
                )
        else:
            gti += hp_income

        result.gross_total_income = max(0, gti)
        result.add_step(f"Gross Total Income: {_fmt(result.gross_total_income)}")

        # --- Step 2: Apply Deductions ---
        deductions_applied = self._apply_deductions(profile, result)
        result.deductions_applied = deductions_applied
        result.total_deductions = sum(d.allowed for d in deductions_applied)
        result.taxable_income = max(0, result.gross_total_income - result.total_deductions)

        if result.total_deductions > 0:
            result.add_step(f"Less: Total deductions: {_fmt(result.total_deductions)}")
        result.add_step(f"Taxable income: {_fmt(result.taxable_income)}")

        # --- Step 3: Tax on slabs ---
        slabs = self.rules.get_slabs(regime, age)
        slab_breakdown, tax_on_slabs = self._compute_slab_tax(result.taxable_income, slabs)
        result.slab_breakdown = slab_breakdown
        result.tax_on_normal_income = tax_on_slabs
        result.add_step(f"Tax on slab rates: {_fmt(tax_on_slabs)}")

        # --- Step 4: Capital Gains Tax ---
        if profile.capital_gains:
            from kara_tax_engine.capital_gains import CapitalGainsCalculator

            cg_calc = CapitalGainsCalculator(fy=self.rules.fy)
            cg_results = cg_calc.compute_multiple(
                [txn.model_dump() for txn in profile.capital_gains]
            )

            special_rate_tax = 0
            slab_rate_gains = 0  # Debt MF gains added to normal income

            for cg in cg_results:
                if cg.section == "slab":
                    # Debt MF — taxable at slab rate, add to normal income
                    slab_rate_gains += max(0, cg.taxable_gain)
                else:
                    # Equity, property, gold, crypto — special rate
                    special_rate_tax += cg.tax_amount

            result.tax_on_special_rates = special_rate_tax
            result.capital_gains_details = cg_results
            result.capital_gains_income = sum(
                cg.taxable_gain for cg in cg_results if cg.taxable_gain > 0
            )

            # Slab-rate gains (debt MF) — recompute slab tax on combined income
            if slab_rate_gains > 0:
                combined_taxable = result.taxable_income + slab_rate_gains
                _, tax_on_combined = self._compute_slab_tax(combined_taxable, slabs)
                result.tax_on_normal_income = tax_on_combined
                result.add_step(f"Debt MF gains added to slab income: +{_fmt(slab_rate_gains)}")
                result.add_step(f"Revised slab tax: {_fmt(tax_on_combined)}")

            if special_rate_tax > 0:
                result.add_step(f"Capital gains tax (special rates): {_fmt(special_rate_tax)}")

        # Recompute total tax before surcharge with updated slab tax
        result.total_tax_before_surcharge = (
            result.tax_on_normal_income + result.tax_on_special_rates
        )

        # --- Step 5: Surcharge ---
        # Surcharge threshold uses total income including capital gains
        surcharge_threshold_income = result.taxable_income + result.capital_gains_income
        surcharge = self._compute_surcharge(
            surcharge_threshold_income, result.total_tax_before_surcharge, regime, age
        )
        result.surcharge_amount = surcharge["amount"]
        result.surcharge_rate = surcharge["rate"]
        result.marginal_relief_surcharge = surcharge["marginal_relief"]
        if surcharge["amount"] > 0:
            result.add_step(
                f"Surcharge @{surcharge['rate'] * 100:.0f}%: {_fmt(surcharge['amount'])}"
            )
            if surcharge["marginal_relief"] > 0:
                result.add_step(
                    f"Marginal relief on surcharge: {_fmt(surcharge['marginal_relief'])}"
                )

        # --- Step 6: Section 87A Rebate (before cess, per Finance Act order) ---
        # The rebate offsets income-tax on normal (slab-rate) income only;
        # it is not available against special-rate capital gains tax.
        rebate = self._compute_rebate_87a(
            result.taxable_income, result.tax_on_normal_income, regime
        )
        result.rebate_87a = rebate["rebate"]
        result.marginal_relief_87a = rebate["marginal_relief"]
        if rebate["rebate"] > 0:
            result.add_step(f"Less: Section 87A rebate: {_fmt(rebate['rebate'])}")
            if rebate["marginal_relief"] > 0:
                result.add_step(
                    f"Marginal relief (87A boundary): {_fmt(rebate['marginal_relief'])}"
                )

        tax_after_rebate = max(0, result.total_tax_before_surcharge - result.rebate_87a)
        tax_plus_surcharge = tax_after_rebate + result.surcharge_amount

        # --- Step 7: Cess (on post-rebate tax + surcharge) ---
        cess_rate = self.rules.cess_rate
        cess = math.ceil(tax_plus_surcharge * cess_rate)
        result.cess_rate = cess_rate
        result.cess_amount = cess
        if cess > 0:
            result.add_step(f"Health & Education Cess @4%: {_fmt(cess)}")

        # --- Step 8: Net Tax Payable ---
        result.total_tax_payable = tax_plus_surcharge + cess
        if result.gross_total_income > 0:
            result.effective_tax_rate = round(
                result.total_tax_payable / result.gross_total_income * 100, 2
            )
        result.add_step(f"Total tax payable: {_fmt(result.total_tax_payable)}")
        result.add_step(f"Effective tax rate: {result.effective_tax_rate}%")

        return result

    def _compute_slab_tax(
        self, taxable_income: int, slabs: list[dict[str, Any]]
    ) -> tuple[list[SlabBreakdown], int]:
        breakdown = []
        total_tax = 0
        remaining = taxable_income

        for slab in slabs:
            lower = slab["lower"]
            upper = slab["upper"]
            rate = slab["rate"]

            if remaining <= 0:
                break

            if upper is None:
                taxable_in_slab = remaining
            else:
                slab_width = upper - lower
                taxable_in_slab = min(remaining, slab_width)

            tax_in_slab = math.ceil(taxable_in_slab * rate)
            total_tax += tax_in_slab
            remaining -= taxable_in_slab

            breakdown.append(
                SlabBreakdown(
                    lower=lower,
                    upper=upper,
                    rate=rate,
                    taxable_in_slab=taxable_in_slab,
                    tax_in_slab=tax_in_slab,
                )
            )

        return breakdown, total_tax

    def _compute_surcharge(
        self, taxable_income: int, tax: int, regime: str, age_category: str = "below_60"
    ) -> dict[str, Any]:
        tiers = self.rules.get_surcharge_tiers(regime)
        max_rate = self.rules.get_max_surcharge_rate(regime)

        # Find applicable tier
        applicable_rate = 0.0
        applicable_threshold = 0
        for tier in tiers:
            if taxable_income > tier["threshold"]:
                applicable_rate = tier["rate"]
                applicable_threshold = tier["threshold"]

        if applicable_rate == 0:
            return {"amount": 0, "rate": 0.0, "marginal_relief": 0}

        # Cap at max surcharge rate
        applicable_rate = min(applicable_rate, max_rate)

        surcharge = math.ceil(tax * applicable_rate)

        # Marginal relief: (tax + surcharge) should not exceed
        # (tax on threshold income) + (income exceeding threshold).
        # Threshold tax must be computed with the taxpayer's own slab set.
        _, tax_at_threshold = self._compute_slab_tax(
            applicable_threshold,
            self.rules.get_slabs(regime, age_category),
        )
        excess_income = taxable_income - applicable_threshold
        total_with_surcharge = tax + surcharge
        marginal_limit = tax_at_threshold + excess_income

        marginal_relief = 0
        if total_with_surcharge > marginal_limit:
            marginal_relief = total_with_surcharge - marginal_limit
            surcharge = max(0, surcharge - marginal_relief)

        return {
            "amount": surcharge,
            "rate": applicable_rate,
            "marginal_relief": marginal_relief,
        }

    def _compute_rebate_87a(
        self, taxable_income: int, tax_on_normal_income: int, regime: str
    ) -> dict[str, Any]:
        """Section 87A rebate against income-tax on slab-rate income (pre-cess)."""
        rebate_rules = self.rules.get_rebate_87a(regime)
        max_income = rebate_rules["max_taxable_income"]
        max_rebate = rebate_rules["max_rebate"]

        if taxable_income <= max_income:
            # Full rebate — slab tax becomes zero (cess then applies on zero)
            rebate = min(tax_on_normal_income, max_rebate) if max_rebate else tax_on_normal_income
            return {"rebate": rebate, "marginal_relief": 0}

        # Marginal relief (new regime only): income-tax payable must not
        # exceed the amount by which taxable income exceeds the threshold.
        excess = taxable_income - max_income
        if regime == "new" and tax_on_normal_income > excess:
            rebate = tax_on_normal_income - excess
            return {"rebate": rebate, "marginal_relief": rebate}

        return {"rebate": 0, "marginal_relief": 0}

    def _apply_deductions(self, profile: TaxProfile, result: TaxBreakdown) -> list[DeductionResult]:
        """Apply deductions respecting caps and regime rules."""
        applied: list[DeductionResult] = []
        regime = profile.regime.value
        ded = profile.deductions

        # In new regime, most deductions are NOT allowed
        is_new = regime == "new"

        # HRA exemption (old regime only)
        if not is_new and profile.hra_details:
            hra_exempt = self._compute_hra_exemption(profile.hra_details)
            if hra_exempt > 0:
                applied.append(
                    DeductionResult(
                        section="10(13A)",
                        claimed=hra_exempt,
                        allowed=hra_exempt,
                        note="HRA exemption",
                    )
                )

        # Section 80C + 80CCC + 80CCD(1) — combined cap ₹1,50,000 (old regime only)
        if not is_new:
            combined_80c = ded.section_80c + ded.section_80ccc + ded.section_80ccd_1
            cap_80c = 150000
            allowed_80c = min(combined_80c, cap_80c)
            if allowed_80c > 0:
                applied.append(
                    DeductionResult(
                        section="80C/80CCC/80CCD(1)",
                        claimed=combined_80c,
                        allowed=allowed_80c,
                        cap=cap_80c,
                        note="Combined cap of ₹1,50,000",
                    )
                )

        # Section 80CCD(1B) — additional ₹50,000 NPS (old regime only)
        if not is_new and ded.section_80ccd_1b > 0:
            allowed = min(ded.section_80ccd_1b, 50000)
            applied.append(
                DeductionResult(
                    section="80CCD(1B)",
                    claimed=ded.section_80ccd_1b,
                    allowed=allowed,
                    cap=50000,
                    note="Additional NPS deduction (old regime only)",
                )
            )

        # Section 80CCD(2) — employer NPS (BOTH regimes)
        if ded.section_80ccd_2 > 0:
            # Cap: 14% of basic for govt, 10% for others (we allow as declared)
            applied.append(
                DeductionResult(
                    section="80CCD(2)",
                    claimed=ded.section_80ccd_2,
                    allowed=ded.section_80ccd_2,
                    note="Employer NPS contribution (available in both regimes)",
                )
            )

        # Section 80D — health insurance (old regime only)
        if not is_new and (ded.section_80d > 0 or ded.section_80d_parents > 0):
            # Self/family: ₹25K (₹50K if senior)
            self_cap = 50000 if profile.age_category != AgeCategory.BELOW_60 else 25000
            allowed_self = min(ded.section_80d, self_cap)
            # Parents: ₹25K, or ₹50K only when senior parents are declared
            parents_cap = 50000 if ded.parents_senior else 25000
            allowed_parents = min(ded.section_80d_parents, parents_cap)
            total_80d = allowed_self + allowed_parents
            if total_80d > 0:
                applied.append(
                    DeductionResult(
                        section="80D",
                        claimed=ded.section_80d + ded.section_80d_parents,
                        allowed=total_80d,
                        cap=self_cap + parents_cap,
                        note="Health insurance premium",
                    )
                )

        # Section 80E — education loan interest (old regime only, no cap)
        if not is_new and ded.section_80e > 0:
            applied.append(
                DeductionResult(
                    section="80E",
                    claimed=ded.section_80e,
                    allowed=ded.section_80e,
                    note="Education loan interest (no cap, up to 8 years)",
                )
            )

        # Section 80G — donations (old regime only).
        # The engine does NOT compute the 50%/100% category split or the
        # 10%-of-adjusted-GTI qualifying limit; the caller must supply the
        # final eligible deduction amount, not the raw donation.
        if not is_new and ded.section_80g > 0:
            applied.append(
                DeductionResult(
                    section="80G",
                    claimed=ded.section_80g,
                    allowed=ded.section_80g,
                    note=(
                        "Donations — enter the eligible deduction amount; the "
                        "50%/100% category and 10%-of-AGTI qualifying limit are "
                        "not auto-computed"
                    ),
                )
            )

        # Section 80TTA / 80TTB (old regime only)
        if not is_new:
            if profile.age_category in (AgeCategory.SENIOR, AgeCategory.SUPER_SENIOR):
                if ded.section_80ttb > 0:
                    allowed = min(ded.section_80ttb, 50000)
                    applied.append(
                        DeductionResult(
                            section="80TTB",
                            claimed=ded.section_80ttb,
                            allowed=allowed,
                            cap=50000,
                            note="Senior citizen savings interest",
                        )
                    )
            else:
                if ded.section_80tta > 0:
                    allowed = min(ded.section_80tta, 10000)
                    applied.append(
                        DeductionResult(
                            section="80TTA",
                            claimed=ded.section_80tta,
                            allowed=allowed,
                            cap=10000,
                            note="Savings account interest",
                        )
                    )

        # Section 80U — disability (old regime only)
        if not is_new and ded.section_80u > 0:
            cap = 125000 if ded.section_80u >= 125000 else 75000
            allowed = min(ded.section_80u, cap)
            applied.append(
                DeductionResult(
                    section="80U",
                    claimed=ded.section_80u,
                    allowed=allowed,
                    cap=cap,
                    note="Person with disability",
                )
            )

        # Section 80DD — dependent disability (old regime only)
        if not is_new and ded.section_80dd > 0:
            cap = 125000 if ded.section_80dd >= 125000 else 75000
            allowed = min(ded.section_80dd, cap)
            applied.append(
                DeductionResult(
                    section="80DD",
                    claimed=ded.section_80dd,
                    allowed=allowed,
                    cap=cap,
                    note="Dependent with disability",
                )
            )

        # Section 24(b) — home loan interest (old regime only for deduction)
        if not is_new and ded.section_24b > 0:
            cap_24b = 200000  # Self-occupied
            allowed = min(ded.section_24b, cap_24b)
            applied.append(
                DeductionResult(
                    section="24(b)",
                    claimed=ded.section_24b,
                    allowed=allowed,
                    cap=cap_24b,
                    note="Home loan interest (self-occupied, ₹2L cap)",
                )
            )

        return applied

    def _compute_hra_exemption(self, hra: HRADetails) -> int:
        """Compute HRA exemption under Section 10(13A) + Rule 2A."""
        if hra.hra_received <= 0 or hra.rent_paid <= 0:
            return 0

        basic = hra.basic_salary
        metro_pct = 0.50 if hra.is_metro else 0.40

        # Exemption = min of:
        # 1. Actual HRA received
        # 2. 50%/40% of basic (metro/non-metro)
        # 3. Rent paid - 10% of basic
        option1 = hra.hra_received
        option2 = math.floor(basic * metro_pct)
        option3 = max(0, hra.rent_paid - math.floor(basic * 0.10))

        return min(option1, option2, option3)
