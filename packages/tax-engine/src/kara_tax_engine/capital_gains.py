"""Capital gains computation engine.

Handles LTCG/STCG for equity, debt, property, gold, and crypto.
"""

from __future__ import annotations

import math
from typing import Any

from kara_tax_engine.loader import RuleSet
from kara_tax_engine.models import (
    AssetClass,
    CapitalGainsResult,
    GainType,
)

# Which YAML file each asset class lives in
_RULE_FILE_MAP: dict[AssetClass, str] = {
    AssetClass.LISTED_EQUITY: "equity",
    AssetClass.EQUITY_MF: "equity",
    AssetClass.DEBT_MF: "debt",
    AssetClass.PROPERTY: "property",
    AssetClass.GOLD: "other",
    AssetClass.UNLISTED_SHARES: "other",
    AssetClass.VDA_CRYPTO: "other",
}


class CapitalGainsCalculator:
    """Compute capital gains tax for various asset classes."""

    def __init__(self, fy: str = "2025-26") -> None:
        self.fy = fy
        self.rules = RuleSet(fy)

    def _load_asset_rule(self, asset: AssetClass) -> dict[str, Any]:
        """Load YAML rule for an asset class."""
        rule_file = _RULE_FILE_MAP[asset]
        data = self.rules.load_capital_gains_rule(rule_file)
        return data["asset_classes"][asset.value]

    def _determine_gain_type(self, holding_months: int, threshold: int | None) -> GainType:
        """Determine STCG vs LTCG from holding period."""
        if threshold is None:
            # Crypto/VDA — holding period irrelevant, treat as STCG for classification
            return GainType.STCG
        return GainType.LTCG if holding_months >= threshold else GainType.STCG

    def _apply_grandfathering(self, purchase_price: int, sale_price: int, fmv: int | None) -> int:
        """Adjust cost of acquisition for grandfathering (pre-31-Jan-2018 equity).

        Returns adjusted cost of acquisition.
        """
        if fmv is None:
            return purchase_price
        # Cost = max(actual_cost, min(FMV, sale_price))
        return max(purchase_price, min(fmv, sale_price))

    def compute(
        self,
        asset_class: str | AssetClass,
        purchase_price: int,
        sale_price: int,
        holding_months: int,
        fmv_31jan2018: int | None = None,
        section_54_amount: int = 0,
        section_54ec_amount: int = 0,
    ) -> CapitalGainsResult:
        """Compute capital gains tax for a single transaction."""
        # Normalize asset class
        if isinstance(asset_class, str):
            asset = AssetClass(asset_class)
        else:
            asset = asset_class

        # Load rule
        rule = self._load_asset_rule(asset)
        threshold = rule["holding_period_months"]
        gain_type = self._determine_gain_type(holding_months, threshold)

        # Get rate config for this gain type
        type_key = "ltcg" if gain_type == GainType.LTCG else "stcg"
        rate_config = rule[type_key]
        section = rate_config["section"]
        rate = rate_config["rate"]  # None for slab-rate assets

        # Compute cost of acquisition (with grandfathering if applicable)
        cost = purchase_price
        note_parts = []

        if (
            fmv_31jan2018 is not None
            and gain_type == GainType.LTCG
            and rule.get("grandfathering") is not None
        ):
            cost = self._apply_grandfathering(purchase_price, sale_price, fmv_31jan2018)
            if cost != purchase_price:
                note_parts.append(f"Grandfathered cost: {cost} (FMV 31-Jan-2018: {fmv_31jan2018})")

        # Total gain
        total_gain = sale_price - cost

        # Exemptions
        exempt_amount = 0

        # Section 54/54EC (property only)
        if section_54_amount > 0 and asset == AssetClass.PROPERTY:
            s54_cap = 10_00_00_000  # Rs 10Cr
            s54 = min(section_54_amount, s54_cap, max(0, total_gain))
            exempt_amount += s54
            if s54 > 0:
                note_parts.append(f"Section 54 exemption: {s54}")

        if section_54ec_amount > 0 and asset == AssetClass.PROPERTY:
            s54ec_cap = 50_00_000  # Rs 50L
            remaining_gain = max(0, total_gain - exempt_amount)
            s54ec = min(section_54ec_amount, s54ec_cap, remaining_gain)
            exempt_amount += s54ec
            if s54ec > 0:
                note_parts.append(f"Section 54EC exemption: {s54ec}")

        # LTCG equity exemption (Rs 1.25L) — applied per-transaction here,
        # but compute_multiple() handles the shared annual cap
        # For single compute(), apply full exemption
        ltcg_exemption = rate_config.get("exemption", 0) if gain_type == GainType.LTCG else 0
        if ltcg_exemption > 0 and total_gain > 0:
            equity_exempt = min(ltcg_exemption, max(0, total_gain - exempt_amount))
            exempt_amount += equity_exempt

        # Taxable gain
        taxable_gain = max(0, total_gain - exempt_amount)

        # Tax computation
        if rate is not None and taxable_gain > 0:
            tax_amount = math.ceil(taxable_gain * rate)
        else:
            tax_amount = 0  # slab-rate or no gain

        # For losses, record but no tax
        if total_gain < 0:
            taxable_gain = total_gain  # negative = loss
            tax_amount = 0

        return CapitalGainsResult(
            asset_class=asset,
            gain_type=gain_type,
            section=section,
            purchase_price=purchase_price,
            sale_price=sale_price,
            total_gain=total_gain,
            exempt_amount=exempt_amount,
            taxable_gain=taxable_gain,
            tax_rate=rate if rate is not None else 0.0,
            tax_amount=tax_amount,
            holding_months=holding_months,
            note="; ".join(note_parts) if note_parts else "",
        )

    def compute_multiple(self, transactions: list[dict[str, Any]]) -> list[CapitalGainsResult]:
        """Process multiple transactions with shared LTCG exemption.

        The Rs 1.25L equity LTCG exemption is shared across ALL equity/equity-MF
        LTCG transactions in a financial year.
        """
        results: list[CapitalGainsResult] = []

        # First pass: compute without LTCG exemption to get raw gains
        raw_results = []
        for txn in transactions:
            # Temporarily compute without equity LTCG exemption
            asset_class = txn["asset_class"]
            if isinstance(asset_class, str):
                asset = AssetClass(asset_class)
            else:
                asset = asset_class

            result = self.compute(
                asset_class=asset,
                purchase_price=txn["purchase_price"],
                sale_price=txn["sale_price"],
                holding_months=txn["holding_months"],
                fmv_31jan2018=txn.get("fmv_31jan2018"),
                section_54_amount=txn.get("section_54_amount", 0),
                section_54ec_amount=txn.get("section_54ec_amount", 0),
            )
            raw_results.append((asset, result))

        # Second pass: distribute shared Rs 1.25L equity LTCG exemption
        equity_ltcg_exemption_remaining = 125000  # Rs 1.25L shared cap

        for asset, result in raw_results:
            if (
                asset in (AssetClass.LISTED_EQUITY, AssetClass.EQUITY_MF)
                and result.gain_type == GainType.LTCG
                and result.total_gain > 0
            ):
                # Remove the per-transaction exemption that compute() applied
                # and re-apply from shared pool
                non_equity_exempt = result.exempt_amount
                # Undo: find equity exemption portion
                rule = self._load_asset_rule(asset)
                per_txn_cap = rule["ltcg"].get("exemption", 0)
                equity_exempt_applied = min(per_txn_cap, max(0, result.total_gain))
                non_equity_exempt = result.exempt_amount - equity_exempt_applied

                # Re-apply from shared pool
                gain_after_other_exemptions = max(0, result.total_gain - non_equity_exempt)
                shared_exempt = min(equity_ltcg_exemption_remaining, gain_after_other_exemptions)
                equity_ltcg_exemption_remaining -= shared_exempt

                new_exempt = non_equity_exempt + shared_exempt
                new_taxable = max(0, result.total_gain - new_exempt)
                rate = result.tax_rate
                new_tax = math.ceil(new_taxable * rate) if rate > 0 and new_taxable > 0 else 0

                result = CapitalGainsResult(
                    asset_class=result.asset_class,
                    gain_type=result.gain_type,
                    section=result.section,
                    purchase_price=result.purchase_price,
                    sale_price=result.sale_price,
                    total_gain=result.total_gain,
                    exempt_amount=new_exempt,
                    taxable_gain=new_taxable,
                    tax_rate=result.tax_rate,
                    tax_amount=new_tax,
                    holding_months=result.holding_months,
                    note=result.note,
                )

            results.append(result)

        return results

    def compute_loss_setoff(self, results: list[CapitalGainsResult]) -> dict[str, Any]:
        """Apply intra-head loss set-off rules for capital gains.

        Rules:
        - STCL can offset STCG first, then LTCG
        - LTCL can offset LTCG only
        - Crypto/VDA losses: NO set-off against anything
        - Crypto/VDA gains: cannot be offset by other losses
        - Carry forward: up to 8 assessment years
        """
        # Separate crypto from non-crypto
        crypto = [r for r in results if r.asset_class == AssetClass.VDA_CRYPTO]
        non_crypto = [r for r in results if r.asset_class != AssetClass.VDA_CRYPTO]

        # Aggregate non-crypto by gain type
        stcg_total = sum(
            r.taxable_gain
            for r in non_crypto
            if r.gain_type == GainType.STCG and r.taxable_gain > 0
        )
        stcl_total = abs(
            sum(
                r.taxable_gain
                for r in non_crypto
                if r.gain_type == GainType.STCG and r.taxable_gain < 0
            )
        )
        ltcg_total = sum(
            r.taxable_gain
            for r in non_crypto
            if r.gain_type == GainType.LTCG and r.taxable_gain > 0
        )
        ltcl_total = abs(
            sum(
                r.taxable_gain
                for r in non_crypto
                if r.gain_type == GainType.LTCG and r.taxable_gain < 0
            )
        )

        # STCL set-off: first against STCG, remainder against LTCG
        stcl_vs_stcg = min(stcl_total, stcg_total)
        stcl_remaining = stcl_total - stcl_vs_stcg
        stcg_after = stcg_total - stcl_vs_stcg

        stcl_vs_ltcg = min(stcl_remaining, ltcg_total)
        stcl_remaining -= stcl_vs_ltcg
        ltcg_after_stcl = ltcg_total - stcl_vs_ltcg

        # LTCL set-off: only against LTCG (after STCL already applied)
        ltcl_vs_ltcg = min(ltcl_total, ltcg_after_stcl)
        ltcl_remaining = ltcl_total - ltcl_vs_ltcg
        ltcg_after = ltcg_after_stcl - ltcl_vs_ltcg

        # Crypto totals (no set-off)
        crypto_gains = sum(r.taxable_gain for r in crypto if r.taxable_gain > 0)
        crypto_losses = abs(sum(r.taxable_gain for r in crypto if r.taxable_gain < 0))

        return {
            "net_stcg": stcg_after,
            "net_ltcg": ltcg_after,
            "crypto_gains": crypto_gains,
            "crypto_losses": crypto_losses,
            "stcl_setoff_against_stcg": stcl_vs_stcg,
            "stcl_setoff_against_ltcg": stcl_vs_ltcg,
            "ltcl_setoff_against_ltcg": ltcl_vs_ltcg,
            "carry_forward_stcl": stcl_remaining,
            "carry_forward_ltcl": ltcl_remaining,
            "carry_forward_crypto": crypto_losses,
            "carry_forward_years": 8,
            "total_carry_forward": stcl_remaining + ltcl_remaining,
        }
