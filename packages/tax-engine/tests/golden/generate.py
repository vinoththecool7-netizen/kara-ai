"""Regenerate expected.json for the golden regression suite.

Run from packages/tax-engine:
    python tests/golden/generate.py

Only regenerate when a computation change is INTENTIONAL; review the diff
of expected.json like you would review tax law.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profiles import PROFILES  # noqa: E402

from kara_tax_engine import TaxComputer, TaxProfile  # noqa: E402

GOLDEN_FIELDS = [
    "gross_total_income",
    "total_deductions",
    "taxable_income",
    "tax_on_normal_income",
    "tax_on_special_rates",
    "surcharge_amount",
    "rebate_87a",
    "cess_amount",
    "total_tax_payable",
]


def compute(profile_kwargs: dict) -> dict:
    computer = TaxComputer(fy="2025-26")
    kwargs = dict(profile_kwargs)
    capital_gains = kwargs.pop("capital_gains", None)
    if capital_gains:
        deductions = kwargs.pop("deductions", None)
        profile = TaxProfile(**kwargs, capital_gains=capital_gains)
        if deductions:
            raise ValueError("deductions+capital_gains profiles not supported here")
        result = computer.compute_from_profile(profile)
    else:
        result = computer.compute(**kwargs)
    return {field: getattr(result, field) for field in GOLDEN_FIELDS}


def main() -> None:
    expected = {name: compute(kwargs) for name, kwargs in PROFILES.items()}
    out = Path(__file__).parent / "expected.json"
    out.write_text(json.dumps(expected, indent=2) + "\n")
    print(f"Wrote {out} ({len(expected)} profiles)")


if __name__ == "__main__":
    main()
