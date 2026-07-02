"""ITR form selection decision tree (AY 2026-27 rules).

Implements the eligibility rules for ITR-1 (Sahaj), ITR-2, ITR-3, and
ITR-4 (Sugam) for individuals/HUF, plus the entity shortcuts for firms,
LLPs, companies, and trusts.
"""

from __future__ import annotations

from pydantic import BaseModel

# ITR-1/ITR-4 income ceiling
_SAHAJ_SUGAM_INCOME_LIMIT = 5_000_000
# From AY 2025-26, ITR-1/ITR-4 may include LTCG u/s 112A up to this amount
_ITR1_LTCG_112A_LIMIT = 125_000
_AGRI_LIMIT = 5_000


class ITRRecommendation(BaseModel):
    form: str
    reason: str
    exclusions_applied: list[str] = []
    note: str = ""


class ITRSelector:
    """Recommend the correct ITR form for a taxpayer's situation."""

    def __init__(self, fy: str = "2025-26") -> None:
        self.fy = fy

    def select(
        self,
        *,
        entity_type: str = "individual",
        residential_status: str = "resident",
        total_income: int = 0,
        has_salary: bool = False,
        house_property_count: int = 0,
        has_business: bool = False,
        is_presumptive: bool = False,
        ltcg_112a_amount: int = 0,
        has_other_capital_gains: bool = False,
        has_foreign_assets: bool = False,
        has_crypto_income: bool = False,
        is_director: bool = False,
        has_unlisted_shares: bool = False,
        agricultural_income: int = 0,
    ) -> ITRRecommendation:
        entity = entity_type.strip().lower()
        is_resident = residential_status.strip().lower() == "resident"

        # ----- entity shortcuts ------------------------------------------
        if entity == "company":
            return ITRRecommendation(form="ITR-6", reason="Companies must file ITR-6")
        if entity in ("firm", "llp", "aop", "boi"):
            return ITRRecommendation(
                form="ITR-5", reason="Firms, LLPs, AOPs, and BOIs file ITR-5"
            )
        if entity in ("trust", "charitable", "political_party"):
            return ITRRecommendation(
                form="ITR-7", reason="Trusts and charitable institutions file ITR-7"
            )

        # ----- shared exclusions for the simplified forms ----------------
        simplified_exclusions: list[str] = []
        if total_income > _SAHAJ_SUGAM_INCOME_LIMIT:
            simplified_exclusions.append("total income exceeds ₹50 lakh")
        if not is_resident:
            simplified_exclusions.append("not an ordinarily resident taxpayer")
        if is_director:
            simplified_exclusions.append("director of a company")
        if has_unlisted_shares:
            simplified_exclusions.append("holds unlisted equity shares")
        if has_foreign_assets:
            simplified_exclusions.append("has foreign assets or foreign income")
        if has_crypto_income:
            simplified_exclusions.append("has virtual digital asset (crypto) income")
        if agricultural_income > _AGRI_LIMIT:
            simplified_exclusions.append("agricultural income exceeds ₹5,000")
        if ltcg_112a_amount > _ITR1_LTCG_112A_LIMIT:
            simplified_exclusions.append("LTCG u/s 112A exceeds ₹1.25 lakh")
        if has_other_capital_gains:
            simplified_exclusions.append("has capital gains other than small 112A LTCG")

        # ----- business income: ITR-4 (presumptive) or ITR-3 -------------
        if has_business:
            if is_presumptive and not simplified_exclusions and house_property_count <= 1:
                return ITRRecommendation(
                    form="ITR-4",
                    reason=(
                        "Resident with presumptive business/professional income "
                        "(44AD/44ADA/44AE) and total income up to ₹50 lakh"
                    ),
                    note=(
                        "May include salary, one house property, and LTCG u/s 112A "
                        "up to ₹1.25 lakh"
                    ),
                )
            reason = "Business or professional income outside the presumptive scheme"
            if is_presumptive and simplified_exclusions:
                reason = (
                    "Presumptive income, but ITR-4 is unavailable: "
                    + "; ".join(simplified_exclusions)
                )
            return ITRRecommendation(
                form="ITR-3",
                reason=reason,
                exclusions_applied=simplified_exclusions,
            )

        # ----- no business income: ITR-1 or ITR-2 ------------------------
        if house_property_count > 1:
            simplified_exclusions.append("more than one house property")

        if not simplified_exclusions:
            return ITRRecommendation(
                form="ITR-1",
                reason=(
                    "Resident individual with salary/pension, at most one house "
                    "property, other sources, and total income up to ₹50 lakh"
                ),
                note=(
                    "Includes LTCG u/s 112A up to ₹1.25 lakh (allowed in ITR-1 "
                    "from AY 2025-26)"
                ),
            )

        return ITRRecommendation(
            form="ITR-2",
            reason=(
                "Individual/HUF without business income, not eligible for ITR-1: "
                + "; ".join(simplified_exclusions)
            ),
            exclusions_applied=simplified_exclusions,
        )
