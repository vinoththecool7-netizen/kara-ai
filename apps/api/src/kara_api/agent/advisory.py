"""Proactive advisory triggers: hints based on tool calls made.

After the agent completes a turn, check which tools ran and suggest
follow-up actions the user might benefit from. These hints are
surfaced as SSE 'advisory' events in the chat stream.
"""
from __future__ import annotations


class AdvisoryTriggers:
    """Generates proactive follow-up hints based on tools called."""

    def check(self, tool_calls_made: list[str]) -> list[str]:
        """Return advisory hint strings based on the tools that just ran.

        Parameters
        ----------
        tool_calls_made:
            List of tool names that were called in the current turn.

        Returns
        -------
        list[str]
            Hints to show the user. May be empty if no advisories apply.
        """
        hints: list[str] = []
        tool_set = set(tool_calls_made)

        for tool_name in tool_calls_made:
            method = self._triggers.get(tool_name)
            if method:
                hint = method(self, tool_set)
                if hint:
                    hints.append(hint)

        # Deduplicate (if same tool called multiple times)
        return list(dict.fromkeys(hints))

    # ---------------------------------------------------------------
    # Trigger methods (one per tool that warrants a follow-up)
    # ---------------------------------------------------------------

    def _after_compute_tax(self, tool_set: set[str]) -> str | None:
        if "compare_regimes" not in tool_set:
            return (
                "I computed your tax under one regime. Would you like me to "
                "compare both regimes to see if you could save more?"
            )
        return None

    def _after_compare_regimes(self, tool_set: set[str]) -> str | None:
        return (
            "Now that we've compared regimes, would you like me to check "
            "for deduction opportunities that could further reduce your tax?"
        )

    def _after_find_deduction_gaps(self, tool_set: set[str]) -> str | None:
        return (
            "Based on your deduction gaps, you could save more by investing in "
            "instruments like ELSS, PPF, or NPS. Want me to compute your "
            "revised tax with these deductions?"
        )

    def _after_compute_capital_gains(self, tool_set: set[str]) -> str | None:
        return (
            "You have capital gains. Would you like me to check if you "
            "qualify for Section 54/54EC exemptions, or explore tax-loss "
            "harvesting strategies?"
        )

    _triggers: dict[str, callable] = {
        "compute_tax": _after_compute_tax,
        "compare_regimes": _after_compare_regimes,
        "find_deduction_gaps": _after_find_deduction_gaps,
        "compute_capital_gains": _after_compute_capital_gains,
    }
