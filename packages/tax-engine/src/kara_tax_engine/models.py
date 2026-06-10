"""Data models for the Kara tax computation engine."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Regime(str, Enum):
    OLD = "old"
    NEW = "new"


class AgeCategory(str, Enum):
    BELOW_60 = "below_60"
    SENIOR = "senior"  # 60-80
    SUPER_SENIOR = "super_senior"  # 80+


class IncomeType(str, Enum):
    SALARY = "salary"
    BUSINESS = "business"
    HOUSE_PROPERTY = "house_property"
    CAPITAL_GAINS = "capital_gains"
    OTHER_SOURCES = "other_sources"


class AssetClass(str, Enum):
    LISTED_EQUITY = "listed_equity"
    EQUITY_MF = "equity_mf"
    DEBT_MF = "debt_mf"
    PROPERTY = "property"
    GOLD = "gold"
    UNLISTED_SHARES = "unlisted_shares"
    VDA_CRYPTO = "vda_crypto"


class GainType(str, Enum):
    STCG = "short_term"
    LTCG = "long_term"


# --- Input Models ---


class SalaryIncome(BaseModel):
    basic: int = 0
    da: int = 0
    hra_received: int = 0
    special_allowance: int = 0
    lta: int = 0
    other_allowances: int = 0
    employer_nps: int = 0  # Section 80CCD(2)
    professional_tax: int = 0
    gross_salary: int = 0  # If set, used directly instead of summing components

    def total(self) -> int:
        if self.gross_salary > 0:
            return self.gross_salary
        return (
            self.basic
            + self.da
            + self.hra_received
            + self.special_allowance
            + self.lta
            + self.other_allowances
        )


class HRADetails(BaseModel):
    hra_received: int = 0
    basic_salary: int = 0  # basic + DA for HRA purposes
    rent_paid: int = 0
    is_metro: bool = False  # Mumbai, Delhi, Kolkata, Chennai


class Deductions(BaseModel):
    """User-declared deductions. The engine enforces caps and regime filtering."""

    section_80c: int = 0
    section_80ccc: int = 0  # Pension fund
    section_80ccd_1: int = 0  # NPS employee contribution (within 80C limit)
    section_80ccd_1b: int = 0  # NPS additional (₹50K, old regime only)
    section_80ccd_2: int = 0  # NPS employer (both regimes)
    section_80d: int = 0  # Health insurance
    section_80d_parents: int = 0  # Parents health insurance
    parents_senior: bool = False  # Parents aged 60+ (raises 80D parents cap to ₹50K)
    section_80e: int = 0  # Education loan interest
    section_80g: int = 0  # Donations
    section_80tta: int = 0  # Savings interest (₹10K)
    section_80ttb: int = 0  # Senior savings interest (₹50K)
    section_80u: int = 0  # Disability
    section_80dd: int = 0  # Dependent disability
    section_24b: int = 0  # Home loan interest (house property)
    hra_exemption: int = 0  # Computed from HRADetails
    lta_exemption: int = 0


class CapitalGainTransaction(BaseModel):
    """Single capital gain/loss transaction input."""

    asset_class: AssetClass
    purchase_price: int
    sale_price: int
    holding_months: int
    fmv_31jan2018: int | None = None  # For grandfathering (pre-2018 equity)
    section_54_amount: int = 0  # Reinvestment exemption (property)
    section_54ec_amount: int = 0  # Bond investment exemption (property)


class TaxProfile(BaseModel):
    """Complete input profile for tax computation."""

    financial_year: str = "2025-26"
    assessment_year: str = "2026-27"
    regime: Regime = Regime.NEW
    age_category: AgeCategory = AgeCategory.BELOW_60
    residential_status: str = "resident"

    # Income
    salary: SalaryIncome | None = None
    gross_salary: int = 0  # Shortcut: set this if you don't have salary components
    business_income: int = 0
    house_property_income: int = 0  # Can be negative (loss)
    other_income: int = 0  # Interest, dividends, etc.

    # Capital gains
    capital_gains: list[CapitalGainTransaction] = Field(default_factory=list)

    # Deductions
    deductions: Deductions = Field(default_factory=Deductions)
    hra_details: HRADetails | None = None

    def get_gross_salary(self) -> int:
        if self.salary:
            return self.salary.total()
        return self.gross_salary


# --- Output Models ---


class SlabBreakdown(BaseModel):
    """Tax computed for a single slab."""

    lower: int
    upper: int | None  # None = no upper bound
    rate: float
    taxable_in_slab: int
    tax_in_slab: int


class DeductionResult(BaseModel):
    """Applied deductions with caps enforced."""

    section: str
    claimed: int
    allowed: int  # After cap enforcement
    cap: int | None = None
    regime_applicable: bool = True
    note: str = ""


class CapitalGainsResult(BaseModel):
    asset_class: AssetClass
    gain_type: GainType
    section: str  # "111A", "112A", "112", etc.
    purchase_price: int
    sale_price: int
    total_gain: int
    exempt_amount: int = 0
    taxable_gain: int
    tax_rate: float
    tax_amount: int
    holding_months: int
    note: str = ""


class TaxBreakdown(BaseModel):
    """Complete tax computation result with full audit trail."""

    regime: Regime
    financial_year: str
    assessment_year: str
    age_category: AgeCategory

    # Step 1: Income
    gross_salary: int = 0
    standard_deduction: int = 0
    net_salary: int = 0
    house_property_income: int = 0
    business_income: int = 0
    capital_gains_income: int = 0
    other_income: int = 0
    gross_total_income: int = 0

    # Step 2: Deductions
    deductions_applied: list[DeductionResult] = Field(default_factory=list)
    total_deductions: int = 0
    taxable_income: int = 0

    # Step 3: Tax on slabs
    slab_breakdown: list[SlabBreakdown] = Field(default_factory=list)
    tax_on_normal_income: int = 0

    # Step 4: Special rate tax (capital gains)
    tax_on_special_rates: int = 0
    capital_gains_details: list[CapitalGainsResult] = Field(default_factory=list)

    # Step 5: Total tax before adjustments
    total_tax_before_surcharge: int = 0

    # Step 6: Surcharge
    surcharge_rate: float = 0.0
    surcharge_amount: int = 0
    marginal_relief_surcharge: int = 0

    # Step 7: Cess
    cess_rate: float = 0.04
    cess_amount: int = 0

    # Step 8: Rebate
    rebate_87a: int = 0
    marginal_relief_87a: int = 0

    # Final
    total_tax_payable: int = 0
    effective_tax_rate: float = 0.0

    # Audit trail
    computation_steps: list[str] = Field(default_factory=list)

    def add_step(self, step: str) -> None:
        self.computation_steps.append(step)


class RegimeComparison(BaseModel):
    old_regime: TaxBreakdown
    new_regime: TaxBreakdown
    recommended_regime: Regime
    savings: int  # Positive = recommended saves this much
    breakeven_deductions: int  # Deduction amount where old = new
    explanation: str = ""


class OptimizationSuggestion(BaseModel):
    section: str
    instrument: str
    suggested_amount: int
    potential_tax_saving: int
    lock_in_years: int | None = None
    expected_return_range: list[float] = Field(default_factory=list)
    note: str = ""


class OptimizationResult(BaseModel):
    current_tax: int
    optimized_tax: int
    total_potential_saving: int
    suggestions: list[OptimizationSuggestion] = Field(default_factory=list)
    section_80c_used: int = 0
    section_80c_remaining: int = 0
    section_80d_used: int = 0
    section_80d_remaining: int = 0
    section_80ccd_1b_used: int = 0
    section_80ccd_1b_remaining: int = 0
