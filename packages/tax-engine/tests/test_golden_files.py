"""Golden-file regression suite: 20 frozen profiles, exact-value assertions.

If any of these fail, either a regression was introduced or a computation
change was intentional — in the latter case regenerate expected.json via
``python tests/golden/generate.py`` and review the diff in code review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_GOLDEN_DIR = Path(__file__).parent / "golden"
sys.path.insert(0, str(_GOLDEN_DIR))
from profiles import PROFILES  # noqa: E402

with open(_GOLDEN_DIR / "expected.json") as f:
    EXPECTED = json.load(f)


def test_every_profile_has_expectations():
    assert set(PROFILES) == set(EXPECTED)
    assert len(PROFILES) == 20


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_golden_profile(name):
    from generate import compute  # golden/ is on sys.path; reuse the builder

    actual = compute(PROFILES[name])
    assert actual == EXPECTED[name], (
        f"Golden mismatch for '{name}'. If this change is intentional, "
        "regenerate tests/golden/expected.json and review the diff."
    )
