"""Tests for AdvisoryTriggers — proactive follow-up hints."""
import pytest

from kara_api.agent.advisory import AdvisoryTriggers


@pytest.fixture
def triggers() -> AdvisoryTriggers:
    return AdvisoryTriggers()


class TestAdvisoryTriggers:
    """Suite covering all advisory trigger rules."""

    def test_compute_tax_suggests_regime_comparison(self, triggers: AdvisoryTriggers):
        """compute_tax alone should suggest comparing regimes."""
        hints = triggers.check(["compute_tax"])
        assert len(hints) == 1
        assert "compare both regimes" in hints[0]

    def test_compute_tax_no_hint_if_compare_also_called(self, triggers: AdvisoryTriggers):
        """compute_tax + compare_regimes should suppress the compute_tax hint."""
        hints = triggers.check(["compute_tax", "compare_regimes"])
        # The compute_tax hint is suppressed; only the compare_regimes hint fires.
        assert not any("compare both regimes" in h for h in hints)

    def test_compare_regimes_suggests_deductions(self, triggers: AdvisoryTriggers):
        """compare_regimes should suggest checking for deduction opportunities."""
        hints = triggers.check(["compare_regimes"])
        assert len(hints) == 1
        assert "deduction opportunities" in hints[0]

    def test_find_deduction_gaps_suggests_instruments(self, triggers: AdvisoryTriggers):
        """find_deduction_gaps should suggest ELSS/PPF/NPS."""
        hints = triggers.check(["find_deduction_gaps"])
        assert len(hints) == 1
        assert "ELSS" in hints[0]
        assert "PPF" in hints[0]
        assert "NPS" in hints[0]

    def test_capital_gains_suggests_exemptions(self, triggers: AdvisoryTriggers):
        """compute_capital_gains should suggest Section 54/54EC exemptions."""
        hints = triggers.check(["compute_capital_gains"])
        assert len(hints) == 1
        assert "54/54EC" in hints[0]

    def test_no_hints_for_search_tax_law(self, triggers: AdvisoryTriggers):
        """search_tax_law should produce no hints."""
        hints = triggers.check(["search_tax_law"])
        assert hints == []

    def test_no_hints_for_get_tds_rate(self, triggers: AdvisoryTriggers):
        """get_tds_rate should produce no hints."""
        hints = triggers.check(["get_tds_rate"])
        assert hints == []

    def test_multiple_tools_returns_multiple_hints(self, triggers: AdvisoryTriggers):
        """compute_tax + compute_capital_gains should yield 2 hints."""
        hints = triggers.check(["compute_tax", "compute_capital_gains"])
        assert len(hints) == 2

    def test_empty_tool_list_returns_no_hints(self, triggers: AdvisoryTriggers):
        """An empty tool list should return no hints."""
        hints = triggers.check([])
        assert hints == []

    def test_hints_are_strings(self, triggers: AdvisoryTriggers):
        """All returned hints must be strings."""
        hints = triggers.check(["compute_tax", "compare_regimes", "find_deduction_gaps", "compute_capital_gains"])
        assert all(isinstance(h, str) for h in hints)
