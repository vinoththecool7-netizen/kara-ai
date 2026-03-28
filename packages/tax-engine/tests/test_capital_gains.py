"""Tests for the capital gains computation engine.

Covers equity (listed + MF), debt MF, grandfathering, and edge cases.
"""

from __future__ import annotations

import math

from kara_tax_engine.capital_gains import CapitalGainsCalculator
from kara_tax_engine.models import (
    AssetClass,
    CapitalGainsResult,
    CapitalGainTransaction,
    GainType,
    Regime,
    TaxProfile,
)

# ===================================================================
# Group A: Equity STCG — 20% rate
# ===================================================================


class TestEquitySTCG:
    """Listed equity short-term capital gains at 20%."""

    def test_equity_stcg_basic(self, cg_calc: CapitalGainsCalculator) -> None:
        """Buy 1L, sell 2L, hold 6 months -> gain 1L, tax 20K."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=6,
        )
        assert result.gain_type == GainType.STCG
        assert result.total_gain == 100_000
        assert result.taxable_gain == 100_000
        assert result.tax_amount == 20_000

    def test_equity_stcg_small_gain(self, cg_calc: CapitalGainsCalculator) -> None:
        """Buy 1L, sell 1.1L, hold 3 months -> gain 10K, tax 2K."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=110_000,
            holding_months=3,
        )
        assert result.total_gain == 10_000
        assert result.tax_amount == 2_000

    def test_equity_stcg_large_gain(self, cg_calc: CapitalGainsCalculator) -> None:
        """Buy 5L, sell 15L, hold 11 months -> gain 10L, tax 2L."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=500_000,
            sale_price=1_500_000,
            holding_months=11,
        )
        assert result.gain_type == GainType.STCG
        assert result.total_gain == 1_000_000
        assert result.tax_amount == 200_000

    def test_equity_stcg_at_boundary(self, cg_calc: CapitalGainsCalculator) -> None:
        """Exactly 11 months — still STCG (threshold is 12)."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=11,
        )
        assert result.gain_type == GainType.STCG

    def test_equity_stcg_section(self, cg_calc: CapitalGainsCalculator) -> None:
        """STCG on listed equity falls under section 111A."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=6,
        )
        assert result.section == "111A"


# ===================================================================
# Group B: Equity LTCG — 12.5% above Rs 1.25L
# ===================================================================


class TestEquityLTCG:
    """Listed equity long-term capital gains at 12.5% above Rs 1.25L exemption."""

    def test_equity_ltcg_basic(self, cg_calc: CapitalGainsCalculator) -> None:
        """Buy 1L, sell 6L, hold 18 months -> gain 5L, exempt 1.25L, taxable 3.75L."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=600_000,
            holding_months=18,
        )
        assert result.gain_type == GainType.LTCG
        assert result.total_gain == 500_000
        assert result.exempt_amount == 125_000
        assert result.taxable_gain == 375_000
        assert result.tax_amount == 46_875  # 375000 * 0.125

    def test_equity_ltcg_at_boundary(self, cg_calc: CapitalGainsCalculator) -> None:
        """Exactly 12 months — qualifies as LTCG."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=600_000,
            holding_months=12,
        )
        assert result.gain_type == GainType.LTCG

    def test_equity_ltcg_large(self, cg_calc: CapitalGainsCalculator) -> None:
        """Buy 10L, sell 30L, hold 24 months -> gain 20L, exempt 1.25L, taxable 18.75L."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=1_000_000,
            sale_price=3_000_000,
            holding_months=24,
        )
        assert result.total_gain == 2_000_000
        assert result.exempt_amount == 125_000
        assert result.taxable_gain == 1_875_000
        # 1875000 * 0.125 = 234375
        assert result.tax_amount == 234_375

    def test_equity_ltcg_rate(self, cg_calc: CapitalGainsCalculator) -> None:
        """Verify LTCG rate is 12.5%."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=600_000,
            holding_months=18,
        )
        assert result.tax_rate == 0.125

    def test_equity_ltcg_section(self, cg_calc: CapitalGainsCalculator) -> None:
        """LTCG on listed equity falls under section 112A."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=600_000,
            holding_months=18,
        )
        assert result.section == "112A"

    def test_equity_ltcg_13_months(self, cg_calc: CapitalGainsCalculator) -> None:
        """13 months is LTCG."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=600_000,
            holding_months=13,
        )
        assert result.gain_type == GainType.LTCG


# ===================================================================
# Group C: LTCG exemption edge cases
# ===================================================================


class TestLTCGExemptionEdges:
    """Edge cases around the Rs 1.25L LTCG exemption."""

    def test_equity_ltcg_below_exemption(self, cg_calc: CapitalGainsCalculator) -> None:
        """Gain = 1L (< 1.25L) -> fully exempt, tax 0."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=18,
        )
        assert result.total_gain == 100_000
        assert result.exempt_amount == 100_000
        assert result.taxable_gain == 0
        assert result.tax_amount == 0

    def test_equity_ltcg_at_exemption(self, cg_calc: CapitalGainsCalculator) -> None:
        """Gain = 1.25L exactly -> fully exempt, tax 0."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=225_000,
            holding_months=18,
        )
        assert result.total_gain == 125_000
        assert result.exempt_amount == 125_000
        assert result.taxable_gain == 0
        assert result.tax_amount == 0

    def test_equity_ltcg_just_above_exemption(self, cg_calc: CapitalGainsCalculator) -> None:
        """Gain = 125001 -> taxable 1, tax 1 (ceil of 0.125)."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=225_001,
            holding_months=18,
        )
        assert result.total_gain == 125_001
        assert result.exempt_amount == 125_000
        assert result.taxable_gain == 1
        assert result.tax_amount == math.ceil(1 * 0.125)  # 1


# ===================================================================
# Group D: Equity MF
# ===================================================================


class TestEquityMF:
    """Equity mutual funds — same rates and thresholds as listed equity."""

    def test_equity_mf_stcg(self, cg_calc: CapitalGainsCalculator) -> None:
        """Equity MF STCG at 20%."""
        result = cg_calc.compute(
            asset_class=AssetClass.EQUITY_MF,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=6,
        )
        assert result.gain_type == GainType.STCG
        assert result.tax_rate == 0.20
        assert result.tax_amount == 20_000

    def test_equity_mf_ltcg(self, cg_calc: CapitalGainsCalculator) -> None:
        """Equity MF LTCG at 12.5% above 1.25L."""
        result = cg_calc.compute(
            asset_class=AssetClass.EQUITY_MF,
            purchase_price=100_000,
            sale_price=600_000,
            holding_months=18,
        )
        assert result.gain_type == GainType.LTCG
        assert result.tax_rate == 0.125
        assert result.total_gain == 500_000
        assert result.exempt_amount == 125_000
        assert result.taxable_gain == 375_000
        assert result.tax_amount == 46_875

    def test_equity_mf_12month_threshold(self, cg_calc: CapitalGainsCalculator) -> None:
        """12 months is LTCG for equity MF; 11 months is STCG."""
        ltcg = cg_calc.compute(
            asset_class=AssetClass.EQUITY_MF,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=12,
        )
        stcg = cg_calc.compute(
            asset_class=AssetClass.EQUITY_MF,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=11,
        )
        assert ltcg.gain_type == GainType.LTCG
        assert stcg.gain_type == GainType.STCG

    def test_equity_mf_ltcg_exemption(self, cg_calc: CapitalGainsCalculator) -> None:
        """Equity MF gets Rs 1.25L LTCG exemption."""
        result = cg_calc.compute(
            asset_class=AssetClass.EQUITY_MF,
            purchase_price=100_000,
            sale_price=225_000,
            holding_months=18,
        )
        assert result.total_gain == 125_000
        assert result.exempt_amount == 125_000
        assert result.tax_amount == 0


# ===================================================================
# Group E: Debt MF
# ===================================================================


class TestDebtMF:
    """Debt mutual funds — taxed at slab rate post-2023 amendment."""

    def test_debt_mf_stcg(self, cg_calc: CapitalGainsCalculator) -> None:
        """Debt MF STCG: slab rate -> rate=0.0, tax=0 (actual tax at slab by TaxComputer)."""
        result = cg_calc.compute(
            asset_class=AssetClass.DEBT_MF,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=12,
        )
        assert result.gain_type == GainType.STCG
        assert result.tax_rate == 0.0
        assert result.tax_amount == 0

    def test_debt_mf_ltcg(self, cg_calc: CapitalGainsCalculator) -> None:
        """Debt MF LTCG: also slab rate regardless of holding period."""
        result = cg_calc.compute(
            asset_class=AssetClass.DEBT_MF,
            purchase_price=100_000,
            sale_price=300_000,
            holding_months=30,
        )
        assert result.gain_type == GainType.LTCG
        assert result.tax_rate == 0.0
        assert result.tax_amount == 0

    def test_debt_mf_no_exemption(self, cg_calc: CapitalGainsCalculator) -> None:
        """Debt MF has zero LTCG exemption."""
        result = cg_calc.compute(
            asset_class=AssetClass.DEBT_MF,
            purchase_price=100_000,
            sale_price=300_000,
            holding_months=30,
        )
        assert result.exempt_amount == 0
        assert result.taxable_gain == 200_000

    def test_debt_mf_section(self, cg_calc: CapitalGainsCalculator) -> None:
        """Debt MF section is 'slab' for both STCG and LTCG."""
        stcg = cg_calc.compute(
            asset_class=AssetClass.DEBT_MF,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=12,
        )
        ltcg = cg_calc.compute(
            asset_class=AssetClass.DEBT_MF,
            purchase_price=100_000,
            sale_price=200_000,
            holding_months=30,
        )
        assert stcg.section == "slab"
        assert ltcg.section == "slab"


# ===================================================================
# Group F: Grandfathering
# ===================================================================


class TestGrandfathering:
    """Pre-31-Jan-2018 equity grandfathering rules."""

    def test_grandfathering_fmv_between(self, cg_calc: CapitalGainsCalculator) -> None:
        """FMV=3L between buy=1L and sell=5L -> cost=3L, gain=2L."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=500_000,
            holding_months=18,
            fmv_31jan2018=300_000,
        )
        # cost = max(100000, min(300000, 500000)) = max(100000, 300000) = 300000
        assert result.total_gain == 200_000  # 500000 - 300000
        assert "Grandfathered cost: 300000" in result.note

    def test_grandfathering_fmv_above_sale(self, cg_calc: CapitalGainsCalculator) -> None:
        """FMV=6L > sell=5L -> cost = min(6L,5L) = 5L -> gain=0."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=500_000,
            holding_months=18,
            fmv_31jan2018=600_000,
        )
        # cost = max(100000, min(600000, 500000)) = max(100000, 500000) = 500000
        assert result.total_gain == 0

    def test_grandfathering_fmv_below_purchase(self, cg_calc: CapitalGainsCalculator) -> None:
        """FMV=80K < buy=1L -> cost stays 1L (no change from grandfathering)."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=500_000,
            holding_months=18,
            fmv_31jan2018=80_000,
        )
        # cost = max(100000, min(80000, 500000)) = max(100000, 80000) = 100000
        assert result.total_gain == 400_000  # 500000 - 100000
        # No grandfathering note since cost didn't change
        assert "Grandfathered cost" not in result.note

    def test_grandfathering_no_fmv(self, cg_calc: CapitalGainsCalculator) -> None:
        """No FMV provided -> use purchase price as-is."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=500_000,
            holding_months=18,
            fmv_31jan2018=None,
        )
        assert result.total_gain == 400_000
        assert "Grandfathered cost" not in result.note

    def test_grandfathering_fmv_equals_purchase(self, cg_calc: CapitalGainsCalculator) -> None:
        """FMV=1L = buy=1L -> cost stays 1L."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=500_000,
            holding_months=18,
            fmv_31jan2018=100_000,
        )
        # cost = max(100000, min(100000, 500000)) = max(100000, 100000) = 100000
        assert result.total_gain == 400_000
        # Cost didn't change, so no grandfathering note
        assert "Grandfathered cost" not in result.note


# ===================================================================
# Group G: Zero/negative gains
# ===================================================================


class TestZeroNegativeGains:
    """Edge cases: zero gain and losses."""

    def test_zero_gain(self, cg_calc: CapitalGainsCalculator) -> None:
        """Buy = sell -> gain 0, tax 0."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=100_000,
            sale_price=100_000,
            holding_months=6,
        )
        assert result.total_gain == 0
        assert result.taxable_gain == 0
        assert result.tax_amount == 0

    def test_loss(self, cg_calc: CapitalGainsCalculator) -> None:
        """Sell < buy -> negative gain, tax 0."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=200_000,
            sale_price=100_000,
            holding_months=6,
        )
        assert result.total_gain == -100_000
        assert result.tax_amount == 0

    def test_loss_taxable_gain_negative(self, cg_calc: CapitalGainsCalculator) -> None:
        """Verify taxable_gain is negative (the loss amount)."""
        result = cg_calc.compute(
            asset_class=AssetClass.LISTED_EQUITY,
            purchase_price=500_000,
            sale_price=300_000,
            holding_months=6,
        )
        assert result.total_gain == -200_000
        assert result.taxable_gain == -200_000
        assert result.tax_amount == 0


# ============================================================
# Group H: Debt MF — slab-rate integration through TaxComputer
# ============================================================


class TestDebtMFIntegration:
    def test_debt_mf_slab_rate_integration(self, computer):
        """Debt MF gain added to slab income increases total tax."""
        profile_without = TaxProfile(gross_salary=1_500_000, regime=Regime.NEW)
        result_without = computer.compute_from_profile(profile_without)

        profile_with = TaxProfile(
            gross_salary=1_500_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.DEBT_MF,
                    purchase_price=500_000,
                    sale_price=700_000,
                    holding_months=6,
                )
            ],
        )
        result_with = computer.compute_from_profile(profile_with)
        assert result_with.total_tax_payable > result_without.total_tax_payable

    def test_debt_mf_no_special_rate_tax(self, computer):
        """Debt MF gains go through slabs, not special rates."""
        profile = TaxProfile(
            gross_salary=1_000_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.DEBT_MF,
                    purchase_price=300_000,
                    sale_price=500_000,
                    holding_months=10,
                )
            ],
        )
        result = computer.compute_from_profile(profile)
        assert result.tax_on_special_rates == 0

    def test_debt_mf_ltcg_still_slab(self, computer):
        """Even with >24 month holding, debt MF post-2023 is slab rate."""
        profile = TaxProfile(
            gross_salary=1_000_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.DEBT_MF,
                    purchase_price=300_000,
                    sale_price=500_000,
                    holding_months=30,
                )
            ],
        )
        result = computer.compute_from_profile(profile)
        assert result.tax_on_special_rates == 0
        assert len(result.capital_gains_details) == 1

    def test_debt_mf_in_capital_gains_details(self, computer):
        """Debt MF transaction appears in capital_gains_details."""
        profile = TaxProfile(
            gross_salary=1_000_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.DEBT_MF,
                    purchase_price=200_000,
                    sale_price=300_000,
                    holding_months=12,
                )
            ],
        )
        result = computer.compute_from_profile(profile)
        assert len(result.capital_gains_details) == 1
        assert result.capital_gains_details[0].asset_class == AssetClass.DEBT_MF


# ============================================================
# Group I: Full TaxComputer integration with capital gains
# ============================================================


class TestCapitalGainsIntegration:
    def test_equity_ltcg_in_profile(self, computer):
        """Equity LTCG appears as special rate tax."""
        profile = TaxProfile(
            gross_salary=1_500_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.LISTED_EQUITY,
                    purchase_price=500_000,
                    sale_price=1_000_000,
                    holding_months=18,
                )
            ],
        )
        result = computer.compute_from_profile(profile)
        # Gain = 500000, exempt = 125000, taxable = 375000, tax = ceil(375000 * 0.125) = 46875
        assert result.tax_on_special_rates == 46875

    def test_equity_stcg_in_profile(self, computer):
        """Equity STCG at 20% appears as special rate tax."""
        profile = TaxProfile(
            gross_salary=1_000_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.LISTED_EQUITY,
                    purchase_price=300_000,
                    sale_price=500_000,
                    holding_months=6,
                )
            ],
        )
        result = computer.compute_from_profile(profile)
        # Gain = 200000, STCG 20%, tax = 40000
        assert result.tax_on_special_rates == 40000

    def test_mixed_equity_debt_in_profile(self, computer):
        """Equity goes to special rates, debt goes to slabs."""
        profile = TaxProfile(
            gross_salary=1_500_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.LISTED_EQUITY,
                    purchase_price=500_000,
                    sale_price=1_000_000,
                    holding_months=18,
                ),
                CapitalGainTransaction(
                    asset_class=AssetClass.DEBT_MF,
                    purchase_price=200_000,
                    sale_price=400_000,
                    holding_months=10,
                ),
            ],
        )
        result = computer.compute_from_profile(profile)
        assert result.tax_on_special_rates == 46875  # equity LTCG only
        assert len(result.capital_gains_details) == 2

    def test_capital_gains_increases_total_tax(self, computer):
        """Adding capital gains increases total tax payable."""
        profile_no_cg = TaxProfile(gross_salary=1_500_000, regime=Regime.NEW)
        result_no_cg = computer.compute_from_profile(profile_no_cg)

        profile_with_cg = TaxProfile(
            gross_salary=1_500_000,
            regime=Regime.NEW,
            capital_gains=[
                CapitalGainTransaction(
                    asset_class=AssetClass.LISTED_EQUITY,
                    purchase_price=200_000,
                    sale_price=700_000,
                    holding_months=15,
                )
            ],
        )
        result_with_cg = computer.compute_from_profile(profile_with_cg)
        assert result_with_cg.total_tax_payable > result_no_cg.total_tax_payable

    def test_no_capital_gains_unchanged(self, computer):
        """Profile with no capital gains produces same result as before."""
        profile = TaxProfile(gross_salary=1_500_000, regime=Regime.NEW)
        result = computer.compute_from_profile(profile)
        assert result.tax_on_special_rates == 0
        assert result.capital_gains_details == []
        assert result.capital_gains_income == 0


# ===================================================================
# Group H: Property LTCG
# ===================================================================


class TestPropertyCapitalGains:
    def test_property_ltcg_basic(self, cg_calc):
        result = cg_calc.compute(AssetClass.PROPERTY, 5_000_000, 8_000_000, 36)
        assert result.gain_type == GainType.LTCG
        assert result.total_gain == 3_000_000
        assert result.tax_rate == 0.125
        assert result.tax_amount == 375_000

    def test_property_stcg_slab(self, cg_calc):
        result = cg_calc.compute(AssetClass.PROPERTY, 5_000_000, 6_000_000, 18)
        assert result.gain_type == GainType.STCG
        assert result.section == "slab"
        assert result.tax_amount == 0  # slab rate handled by TaxComputer

    def test_property_ltcg_section(self, cg_calc):
        result = cg_calc.compute(AssetClass.PROPERTY, 5_000_000, 8_000_000, 36)
        assert result.section == "112"

    def test_property_24month_threshold(self, cg_calc):
        ltcg = cg_calc.compute(AssetClass.PROPERTY, 5_000_000, 8_000_000, 24)
        stcg = cg_calc.compute(AssetClass.PROPERTY, 5_000_000, 8_000_000, 23)
        assert ltcg.gain_type == GainType.LTCG
        assert stcg.gain_type == GainType.STCG

    def test_property_loss(self, cg_calc):
        result = cg_calc.compute(AssetClass.PROPERTY, 8_000_000, 5_000_000, 36)
        assert result.total_gain == -3_000_000
        assert result.tax_amount == 0


# ===================================================================
# Group I: Section 54 Exemption
# ===================================================================


class TestSection54Exemption:
    def test_section_54_full_exemption(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.PROPERTY, 5_000_000, 8_000_000, 36, section_54_amount=3_000_000
        )
        assert result.exempt_amount == 3_000_000
        assert result.taxable_gain == 0
        assert result.tax_amount == 0

    def test_section_54_partial_exemption(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.PROPERTY, 5_000_000, 10_000_000, 36, section_54_amount=2_000_000
        )
        assert result.exempt_amount == 2_000_000
        assert result.taxable_gain == 3_000_000
        assert result.tax_amount == math.ceil(3_000_000 * 0.125)

    def test_section_54_cap_10cr(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.PROPERTY, 5_00_00_000, 20_00_00_000, 36, section_54_amount=12_00_00_000
        )
        assert result.exempt_amount == 10_00_00_000  # Capped at 10Cr

    def test_section_54_non_property_ignored(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.LISTED_EQUITY, 500_000, 1_000_000, 18, section_54_amount=3_000_000
        )
        # Section 54 should not apply to equity — only LTCG exemption of 1.25L
        assert result.exempt_amount == 125_000  # Only equity LTCG exemption


# ===================================================================
# Group J: Section 54EC Exemption
# ===================================================================


class TestSection54ECExemption:
    def test_section_54ec_basic(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.PROPERTY, 5_000_000, 13_000_000, 36, section_54ec_amount=5_000_000
        )
        assert result.exempt_amount == 5_000_000
        assert result.taxable_gain == 3_000_000

    def test_section_54ec_cap_50l(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.PROPERTY, 5_000_000, 13_000_000, 36, section_54ec_amount=6_000_000
        )
        assert result.exempt_amount == 5_000_000  # Capped at 50L

    def test_section_54_and_54ec_combined(self, cg_calc):
        result = cg_calc.compute(
            AssetClass.PROPERTY,
            5_000_000,
            15_000_000,
            36,
            section_54_amount=6_000_000,
            section_54ec_amount=4_000_000,
        )
        # Total gain = 10_000_000. Section 54: 6_000_000, Section 54EC: 4_000_000
        assert result.exempt_amount == 10_000_000
        assert result.taxable_gain == 0


# ===================================================================
# Group K: Gold LTCG/STCG
# ===================================================================


class TestGoldCapitalGains:
    def test_gold_ltcg(self, cg_calc):
        result = cg_calc.compute(AssetClass.GOLD, 500_000, 800_000, 30)
        assert result.gain_type == GainType.LTCG
        assert result.tax_rate == 0.125
        assert result.tax_amount == math.ceil(300_000 * 0.125)

    def test_gold_stcg_slab(self, cg_calc):
        result = cg_calc.compute(AssetClass.GOLD, 500_000, 800_000, 12)
        assert result.section == "slab"
        assert result.tax_amount == 0  # slab rate

    def test_gold_24month_threshold(self, cg_calc):
        ltcg = cg_calc.compute(AssetClass.GOLD, 500_000, 800_000, 24)
        stcg = cg_calc.compute(AssetClass.GOLD, 500_000, 800_000, 23)
        assert ltcg.gain_type == GainType.LTCG
        assert stcg.gain_type == GainType.STCG

    def test_unlisted_shares_ltcg(self, cg_calc):
        result = cg_calc.compute(AssetClass.UNLISTED_SHARES, 500_000, 800_000, 30)
        assert result.tax_rate == 0.125
        assert result.section == "112"


# ===================================================================
# Group L: Crypto/VDA
# ===================================================================


class TestCryptoVDA:
    def test_crypto_30_percent(self, cg_calc):
        result = cg_calc.compute(AssetClass.VDA_CRYPTO, 100_000, 300_000, 6)
        assert result.tax_rate == 0.30
        assert result.tax_amount == 60_000

    def test_crypto_long_hold_still_30(self, cg_calc):
        result = cg_calc.compute(AssetClass.VDA_CRYPTO, 100_000, 300_000, 36)
        assert result.tax_rate == 0.30
        assert result.tax_amount == 60_000

    def test_crypto_section_115bbh(self, cg_calc):
        result = cg_calc.compute(AssetClass.VDA_CRYPTO, 100_000, 300_000, 6)
        assert result.section == "115BBH"

    def test_crypto_loss(self, cg_calc):
        result = cg_calc.compute(AssetClass.VDA_CRYPTO, 300_000, 100_000, 6)
        assert result.total_gain == -200_000
        assert result.tax_amount == 0

    def test_crypto_no_exemption(self, cg_calc):
        result = cg_calc.compute(AssetClass.VDA_CRYPTO, 100_000, 300_000, 36)
        assert result.exempt_amount == 0


# ===================================================================
# Group M: Loss set-off
# ===================================================================


class TestLossSetoff:
    def test_stcl_offsets_stcg(self, cg_calc):
        results = [
            cg_calc.compute(AssetClass.LISTED_EQUITY, 300_000, 800_000, 6),  # STCG +500K
            cg_calc.compute(AssetClass.GOLD, 500_000, 300_000, 12),  # STCL -200K (slab, but loss)
        ]
        # For gold STCL, taxable_gain should be negative
        setoff = cg_calc.compute_loss_setoff(results)
        assert setoff["net_stcg"] == 300_000  # 500K - 200K

    def test_stcl_offsets_ltcg_after_stcg(self, cg_calc):
        r_stcg = CapitalGainsResult(
            asset_class=AssetClass.LISTED_EQUITY,
            gain_type=GainType.STCG,
            section="111A",
            purchase_price=400_000,
            sale_price=500_000,
            total_gain=100_000,
            taxable_gain=100_000,
            tax_rate=0.20,
            tax_amount=20_000,
            holding_months=6,
        )
        r_stcl = CapitalGainsResult(
            asset_class=AssetClass.GOLD,
            gain_type=GainType.STCG,
            section="slab",
            purchase_price=500_000,
            sale_price=200_000,
            total_gain=-300_000,
            taxable_gain=-300_000,
            tax_rate=0.0,
            tax_amount=0,
            holding_months=6,
        )
        r_ltcg = CapitalGainsResult(
            asset_class=AssetClass.PROPERTY,
            gain_type=GainType.LTCG,
            section="112",
            purchase_price=5_000_000,
            sale_price=8_000_000,
            total_gain=3_000_000,
            taxable_gain=3_000_000,
            tax_rate=0.125,
            tax_amount=375_000,
            holding_months=36,
        )
        setoff = cg_calc.compute_loss_setoff([r_stcg, r_stcl, r_ltcg])
        assert setoff["stcl_setoff_against_stcg"] == 100_000
        assert setoff["stcl_setoff_against_ltcg"] == 200_000
        assert setoff["net_stcg"] == 0
        assert setoff["net_ltcg"] == 2_800_000

    def test_ltcl_offsets_ltcg_only(self, cg_calc):
        r_stcg = CapitalGainsResult(
            asset_class=AssetClass.LISTED_EQUITY,
            gain_type=GainType.STCG,
            section="111A",
            purchase_price=300_000,
            sale_price=800_000,
            total_gain=500_000,
            taxable_gain=500_000,
            tax_rate=0.20,
            tax_amount=100_000,
            holding_months=6,
        )
        r_ltcl = CapitalGainsResult(
            asset_class=AssetClass.PROPERTY,
            gain_type=GainType.LTCG,
            section="112",
            purchase_price=8_000_000,
            sale_price=6_000_000,
            total_gain=-2_000_000,
            taxable_gain=-2_000_000,
            tax_rate=0.125,
            tax_amount=0,
            holding_months=36,
        )
        setoff = cg_calc.compute_loss_setoff([r_stcg, r_ltcl])
        assert setoff["net_stcg"] == 500_000  # LTCL cannot offset STCG
        assert setoff["carry_forward_ltcl"] == 2_000_000

    def test_crypto_excluded_from_setoff(self, cg_calc):
        r_crypto_loss = CapitalGainsResult(
            asset_class=AssetClass.VDA_CRYPTO,
            gain_type=GainType.STCG,
            section="115BBH",
            purchase_price=500_000,
            sale_price=200_000,
            total_gain=-300_000,
            taxable_gain=-300_000,
            tax_rate=0.30,
            tax_amount=0,
            holding_months=6,
        )
        r_equity_gain = CapitalGainsResult(
            asset_class=AssetClass.LISTED_EQUITY,
            gain_type=GainType.STCG,
            section="111A",
            purchase_price=300_000,
            sale_price=800_000,
            total_gain=500_000,
            taxable_gain=500_000,
            tax_rate=0.20,
            tax_amount=100_000,
            holding_months=6,
        )
        setoff = cg_calc.compute_loss_setoff([r_crypto_loss, r_equity_gain])
        assert setoff["net_stcg"] == 500_000  # Crypto loss excluded
        assert setoff["crypto_losses"] == 300_000


# ===================================================================
# Group N: Loss carry forward
# ===================================================================


class TestLossCarryForward:
    def test_carry_forward_unabsorbed_stcl(self, cg_calc):
        r_stcl = CapitalGainsResult(
            asset_class=AssetClass.GOLD,
            gain_type=GainType.STCG,
            section="slab",
            purchase_price=500_000,
            sale_price=0,
            total_gain=-500_000,
            taxable_gain=-500_000,
            tax_rate=0.0,
            tax_amount=0,
            holding_months=6,
        )
        setoff = cg_calc.compute_loss_setoff([r_stcl])
        assert setoff["carry_forward_stcl"] == 500_000
        assert setoff["total_carry_forward"] == 500_000

    def test_carry_forward_unabsorbed_ltcl(self, cg_calc):
        r_ltcl = CapitalGainsResult(
            asset_class=AssetClass.PROPERTY,
            gain_type=GainType.LTCG,
            section="112",
            purchase_price=8_000_000,
            sale_price=5_000_000,
            total_gain=-3_000_000,
            taxable_gain=-3_000_000,
            tax_rate=0.125,
            tax_amount=0,
            holding_months=36,
        )
        r_stcg = CapitalGainsResult(
            asset_class=AssetClass.LISTED_EQUITY,
            gain_type=GainType.STCG,
            section="111A",
            purchase_price=100_000,
            sale_price=200_000,
            total_gain=100_000,
            taxable_gain=100_000,
            tax_rate=0.20,
            tax_amount=20_000,
            holding_months=6,
        )
        setoff = cg_calc.compute_loss_setoff([r_ltcl, r_stcg])
        assert setoff["carry_forward_ltcl"] == 3_000_000  # LTCL cannot offset STCG
        assert setoff["net_stcg"] == 100_000

    def test_carry_forward_8_years(self, cg_calc):
        r = CapitalGainsResult(
            asset_class=AssetClass.GOLD,
            gain_type=GainType.STCG,
            section="slab",
            purchase_price=500_000,
            sale_price=300_000,
            total_gain=-200_000,
            taxable_gain=-200_000,
            tax_rate=0.0,
            tax_amount=0,
            holding_months=6,
        )
        setoff = cg_calc.compute_loss_setoff([r])
        assert setoff["carry_forward_years"] == 8


# ===================================================================
# Group O: Mixed assets
# ===================================================================


class TestMixedAssets:
    def test_mixed_equity_property_crypto(self, cg_calc):
        results = [
            cg_calc.compute(AssetClass.LISTED_EQUITY, 100_000, 600_000, 18),  # Equity LTCG
            cg_calc.compute(AssetClass.PROPERTY, 5_000_000, 8_000_000, 36),  # Property LTCG
            cg_calc.compute(AssetClass.VDA_CRYPTO, 100_000, 300_000, 6),  # Crypto
        ]
        assert len(results) == 3
        assert results[0].asset_class == AssetClass.LISTED_EQUITY
        assert results[1].asset_class == AssetClass.PROPERTY
        assert results[2].asset_class == AssetClass.VDA_CRYPTO
        assert results[2].tax_rate == 0.30

    def test_compute_multiple_all_asset_classes(self, cg_calc):
        txns = [
            {
                "asset_class": "listed_equity",
                "purchase_price": 100_000,
                "sale_price": 200_000,
                "holding_months": 18,
            },
            {
                "asset_class": "equity_mf",
                "purchase_price": 100_000,
                "sale_price": 200_000,
                "holding_months": 18,
            },
            {
                "asset_class": "debt_mf",
                "purchase_price": 100_000,
                "sale_price": 200_000,
                "holding_months": 30,
            },
            {
                "asset_class": "property",
                "purchase_price": 5_000_000,
                "sale_price": 8_000_000,
                "holding_months": 36,
            },
            {
                "asset_class": "gold",
                "purchase_price": 200_000,
                "sale_price": 400_000,
                "holding_months": 30,
            },
            {
                "asset_class": "unlisted_shares",
                "purchase_price": 100_000,
                "sale_price": 300_000,
                "holding_months": 30,
            },
            {
                "asset_class": "vda_crypto",
                "purchase_price": 50_000,
                "sale_price": 150_000,
                "holding_months": 6,
            },
        ]
        results = cg_calc.compute_multiple(txns)
        assert len(results) == 7

    def test_loss_setoff_mixed_portfolio(self, cg_calc):
        results = [
            CapitalGainsResult(
                asset_class=AssetClass.LISTED_EQUITY,
                gain_type=GainType.STCG,
                section="111A",
                purchase_price=500_000,
                sale_price=800_000,
                total_gain=300_000,
                taxable_gain=300_000,
                tax_rate=0.20,
                tax_amount=60_000,
                holding_months=6,
            ),
            CapitalGainsResult(
                asset_class=AssetClass.GOLD,
                gain_type=GainType.STCG,
                section="slab",
                purchase_price=400_000,
                sale_price=200_000,
                total_gain=-200_000,
                taxable_gain=-200_000,
                tax_rate=0.0,
                tax_amount=0,
                holding_months=12,
            ),
            CapitalGainsResult(
                asset_class=AssetClass.PROPERTY,
                gain_type=GainType.LTCG,
                section="112",
                purchase_price=5_000_000,
                sale_price=9_000_000,
                total_gain=4_000_000,
                taxable_gain=4_000_000,
                tax_rate=0.125,
                tax_amount=500_000,
                holding_months=36,
            ),
        ]
        setoff = cg_calc.compute_loss_setoff(results)
        assert setoff["net_stcg"] == 100_000  # 300K - 200K
        assert setoff["net_ltcg"] == 4_000_000
        assert setoff["total_carry_forward"] == 0
