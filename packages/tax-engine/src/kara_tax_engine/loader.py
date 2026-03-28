"""YAML rule file loader for the Kara tax engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).parent / "rules"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


class RuleSet:
    """Loaded rules for a specific financial year."""

    def __init__(self, fy: str) -> None:
        self.fy = fy
        self.fy_dir = RULES_DIR / f"fy_{fy.replace('-', '_')}"
        if not self.fy_dir.exists():
            available = [d.name for d in RULES_DIR.iterdir() if d.is_dir()]
            raise ValueError(f"No rules found for FY {fy}. Available: {available}")
        self._cache: dict[str, Any] = {}

    def _load(self, relative_path: str) -> dict[str, Any]:
        if relative_path not in self._cache:
            path = self.fy_dir / relative_path
            if not path.exists():
                raise FileNotFoundError(f"Rule file not found: {path}")
            self._cache[relative_path] = _load_yaml(path)
        return self._cache[relative_path]

    @property
    def meta(self) -> dict[str, Any]:
        return self._load("meta.yaml")

    @property
    def new_regime_slabs(self) -> dict[str, Any]:
        return self._load("slabs/new_regime.yaml")

    @property
    def old_regime_slabs(self) -> dict[str, Any]:
        return self._load("slabs/old_regime.yaml")

    @property
    def cess_rate(self) -> float:
        return self.meta["cess_rate"]

    @property
    def standard_deduction(self) -> dict[str, int]:
        return self.meta["standard_deduction"]

    def get_slabs(self, regime: str, age_category: str = "below_60") -> list[dict[str, Any]]:
        if regime == "new":
            return self.new_regime_slabs["slabs"]
        else:
            slabs_data = self.old_regime_slabs["slabs"]
            if age_category in slabs_data:
                return slabs_data[age_category]
            return slabs_data["below_60"]

    def get_rebate_87a(self, regime: str) -> dict[str, Any]:
        if regime == "new":
            return self.new_regime_slabs["rebate_87a"]
        return self.old_regime_slabs["rebate_87a"]

    def get_surcharge_tiers(self, regime: str) -> list[dict[str, Any]]:
        data = self.new_regime_slabs if regime == "new" else self.old_regime_slabs
        return data["surcharge"]["tiers"]

    def get_max_surcharge_rate(self, regime: str) -> float:
        data = self.new_regime_slabs if regime == "new" else self.old_regime_slabs
        return data["surcharge"]["max_surcharge_rate"]

    def get_standard_deduction(self, regime: str) -> int:
        return self.standard_deduction[regime]

    def load_deduction_rule(self, section: str) -> dict[str, Any]:
        return self._load(f"deductions/{section}.yaml")

    def load_capital_gains_rule(self, asset_class: str) -> dict[str, Any]:
        return self._load(f"capital_gains/{asset_class}.yaml")
