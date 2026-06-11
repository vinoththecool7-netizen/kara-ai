"""Kara Tax Engine — Deterministic Indian income tax computation.

Usage:
    from kara_tax_engine import TaxComputer

    computer = TaxComputer(fy="2025-26")
    result = computer.compute(gross_salary=1_500_000, regime="new")
    print(result.total_tax_payable)
"""

from kara_tax_engine.advance_tax import (
    AdvanceTaxCalculator,
    AdvanceTaxInstallment,
    AdvanceTaxSchedule,
)
from kara_tax_engine.capital_gains import CapitalGainsCalculator
from kara_tax_engine.comparator import RegimeComparator
from kara_tax_engine.computer import TaxComputer
from kara_tax_engine.interest import (
    InterestResult,
    interest_234a,
    interest_234b,
    interest_234c,
)
from kara_tax_engine.itr_selector import ITRRecommendation, ITRSelector
from kara_tax_engine.models import (
    AgeCategory,
    CapitalGainsResult,
    CapitalGainTransaction,
    DeductionResult,
    Deductions,
    HRADetails,
    OptimizationResult,
    OptimizationSuggestion,
    Regime,
    RegimeComparison,
    SalaryIncome,
    SlabBreakdown,
    TaxBreakdown,
    TaxProfile,
)
from kara_tax_engine.optimizer import DeductionOptimizer
from kara_tax_engine.tds import TDSCalculator, TDSResult

__version__ = "0.1.0"

__all__ = [
    "AdvanceTaxCalculator",
    "AdvanceTaxInstallment",
    "AdvanceTaxSchedule",
    "AgeCategory",
    "CapitalGainsCalculator",
    "ITRRecommendation",
    "ITRSelector",
    "InterestResult",
    "TDSCalculator",
    "TDSResult",
    "interest_234a",
    "interest_234b",
    "interest_234c",
    "CapitalGainsResult",
    "CapitalGainTransaction",
    "DeductionOptimizer",
    "DeductionResult",
    "Deductions",
    "HRADetails",
    "OptimizationResult",
    "OptimizationSuggestion",
    "Regime",
    "RegimeComparator",
    "RegimeComparison",
    "SalaryIncome",
    "SlabBreakdown",
    "TaxBreakdown",
    "TaxComputer",
    "TaxProfile",
]
