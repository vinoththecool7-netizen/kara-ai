"""Kara Tax Engine — Deterministic Indian income tax computation.

Usage:
    from kara_tax_engine import TaxComputer

    computer = TaxComputer(fy="2025-26")
    result = computer.compute(gross_salary=1_500_000, regime="new")
    print(result.total_tax_payable)
"""

from kara_tax_engine.capital_gains import CapitalGainsCalculator
from kara_tax_engine.comparator import RegimeComparator
from kara_tax_engine.computer import TaxComputer
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

__version__ = "0.1.0"

__all__ = [
    "AgeCategory",
    "CapitalGainsCalculator",
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
