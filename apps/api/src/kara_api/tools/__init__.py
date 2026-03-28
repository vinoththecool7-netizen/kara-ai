"""Tool integration utilities for Kara."""

from kara_api.tools.executor import ToolExecutionError, ToolRegistry, ToolResult
from kara_api.tools.schemas import (
    ALL_TOOLS,
    CALCULATE_ADVANCE_TAX,
    COMPARE_REGIMES,
    COMPUTE_CAPITAL_GAINS,
    COMPUTE_TAX,
    FIND_DEDUCTION_GAPS,
    GET_TDS_RATE,
    SEARCH_TAX_LAW,
    SELECT_ITR_FORM,
    TOOL_MAP,
)

__all__ = [
    "ALL_TOOLS",
    "CALCULATE_ADVANCE_TAX",
    "COMPARE_REGIMES",
    "COMPUTE_CAPITAL_GAINS",
    "COMPUTE_TAX",
    "FIND_DEDUCTION_GAPS",
    "GET_TDS_RATE",
    "SEARCH_TAX_LAW",
    "SELECT_ITR_FORM",
    "TOOL_MAP",
    "ToolExecutionError",
    "ToolRegistry",
    "ToolResult",
]
