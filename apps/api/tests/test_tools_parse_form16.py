"""Tests for the parse_form16 tool registration in ToolRegistry."""
from __future__ import annotations

import base64
import json

import pytest

from kara_api.llm.models import ToolCall
from kara_api.tools.executor import ToolRegistry
from tests.fixtures.form16_factory import make_form16_standard


@pytest.fixture
def registry() -> ToolRegistry:
    """ToolRegistry with default dependencies (no search/DB needed for these tests)."""
    return ToolRegistry()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestParseForm16Registration:
    def test_handler_registered(self, registry: ToolRegistry):
        assert "parse_form16" in registry._handlers

    def test_parse_form16_in_all_tools(self):
        from kara_api.tools.schemas import ALL_TOOLS

        tool_names = [t.name for t in ALL_TOOLS]
        assert "parse_form16" in tool_names

    def test_parse_form16_exported_from_tools_init(self):
        from kara_api.tools import PARSE_FORM16

        assert PARSE_FORM16.name == "parse_form16"


# ---------------------------------------------------------------------------
# Round-trip: base64-encode a fake PDF, execute tool, inspect result
# ---------------------------------------------------------------------------


class TestParseForm16ToolRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_part_a_tan(self, registry: ToolRegistry):
        pdf_bytes = make_form16_standard()
        b64 = base64.b64encode(pdf_bytes).decode()
        result = await registry._handle_parse_form16({"pdf_base64": b64})
        assert result["part_a"]["employer_tan"] is not None

    @pytest.mark.asyncio
    async def test_round_trip_part_b_gross_salary(self, registry: ToolRegistry):
        pdf_bytes = make_form16_standard()
        b64 = base64.b64encode(pdf_bytes).decode()
        result = await registry._handle_parse_form16({"pdf_base64": b64})
        assert result["part_b"]["gross_salary"] == 1200000

    @pytest.mark.asyncio
    async def test_round_trip_via_execute(self, registry: ToolRegistry):
        """Test the full execute() path returns a JSON-parseable ToolResult."""
        pdf_bytes = make_form16_standard()
        b64 = base64.b64encode(pdf_bytes).decode()
        tc = ToolCall(id="tc_001", name="parse_form16", arguments={"pdf_base64": b64})
        tool_result = await registry.execute(tc)
        assert tool_result.is_error is False
        data = json.loads(tool_result.content)
        assert "part_a" in data
        assert data["part_a"]["employer_tan"] is not None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestParseForm16ToolErrors:
    @pytest.mark.asyncio
    async def test_invalid_base64_raises_value_error(self, registry: ToolRegistry):
        with pytest.raises(Exception):
            await registry._handle_parse_form16({"pdf_base64": "!!not_base64!!"})

    @pytest.mark.asyncio
    async def test_garbage_pdf_returns_is_error_true(self, registry: ToolRegistry):
        """Garbage bytes should result in is_error=True from execute()."""
        b64 = base64.b64encode(b"this is not a pdf").decode()
        tc = ToolCall(id="tc_002", name="parse_form16", arguments={"pdf_base64": b64})
        tool_result = await registry.execute(tc)
        assert tool_result.is_error is True
