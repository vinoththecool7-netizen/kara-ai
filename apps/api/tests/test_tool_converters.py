"""Tests for kara_api.tools.converters -- provider wire-format conversions."""
from __future__ import annotations

import json

import pytest

from kara_api.llm.models import ToolCall, ToolDefinition
from kara_api.tools.converters import (
    parse_anthropic_tool_calls,
    parse_openai_tool_calls,
    to_anthropic_tools,
    to_openai_tools,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_tools() -> list[ToolDefinition]:
    """Two representative tool definitions."""
    return [
        ToolDefinition(
            name="compute_tax",
            description="Compute income-tax for a given regime and income.",
            parameters={
                "type": "object",
                "properties": {
                    "regime": {"type": "string", "enum": ["old", "new"]},
                    "income": {"type": "number"},
                },
                "required": ["regime", "income"],
            },
        ),
        ToolDefinition(
            name="search_sections",
            description="Search the knowledge base for relevant tax sections.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        ),
    ]


# ===================================================================
# OpenAI conversion
# ===================================================================

class TestOpenAIConversion:
    """to_openai_tools and parse_openai_tool_calls."""

    def test_to_openai_tools_structure(self, sample_tools: list[ToolDefinition]) -> None:
        """Each tool must be wrapped in {"type": "function", "function": {...}}."""
        result = to_openai_tools(sample_tools)

        assert len(result) == 2
        for entry, original in zip(result, sample_tools):
            assert entry["type"] == "function"
            fn = entry["function"]
            assert fn["name"] == original.name
            assert fn["description"] == original.description
            assert fn["parameters"] == original.parameters

    def test_parse_openai_tool_calls(self) -> None:
        """Parse a single tool call with JSON-string arguments."""
        raw = [
            {
                "id": "call_001",
                "function": {
                    "name": "compute_tax",
                    "arguments": json.dumps({"regime": "new", "income": 1_200_000}),
                },
            },
        ]
        parsed = parse_openai_tool_calls(raw)

        assert len(parsed) == 1
        tc = parsed[0]
        assert isinstance(tc, ToolCall)
        assert tc.id == "call_001"
        assert tc.name == "compute_tax"
        assert tc.arguments == {"regime": "new", "income": 1_200_000}

    def test_parse_openai_multiple_calls(self) -> None:
        """Multiple tool calls in a single response are all parsed."""
        raw = [
            {
                "id": "call_a",
                "function": {
                    "name": "compute_tax",
                    "arguments": json.dumps({"regime": "old", "income": 800_000}),
                },
            },
            {
                "id": "call_b",
                "function": {
                    "name": "search_sections",
                    "arguments": json.dumps({"query": "80C deduction"}),
                },
            },
        ]
        parsed = parse_openai_tool_calls(raw)

        assert len(parsed) == 2
        assert parsed[0].id == "call_a"
        assert parsed[0].name == "compute_tax"
        assert parsed[0].arguments == {"regime": "old", "income": 800_000}
        assert parsed[1].id == "call_b"
        assert parsed[1].name == "search_sections"
        assert parsed[1].arguments == {"query": "80C deduction"}


# ===================================================================
# Anthropic conversion
# ===================================================================

class TestAnthropicConversion:
    """to_anthropic_tools and parse_anthropic_tool_calls."""

    def test_to_anthropic_tools_structure(self, sample_tools: list[ToolDefinition]) -> None:
        """Must use 'input_schema' (not 'parameters') and have no 'type' wrapper."""
        result = to_anthropic_tools(sample_tools)

        assert len(result) == 2
        for entry, original in zip(result, sample_tools):
            assert entry["name"] == original.name
            assert entry["description"] == original.description
            assert entry["input_schema"] == original.parameters
            # Must NOT have an OpenAI-style "type"/"function" wrapper.
            assert "type" not in entry
            assert "function" not in entry
            assert "parameters" not in entry

    def test_parse_anthropic_tool_calls(self) -> None:
        """Extract tool_use blocks with id, name, and (already-parsed) input."""
        blocks = [
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "compute_tax",
                "input": {"regime": "new", "income": 1_500_000},
            },
        ]
        parsed = parse_anthropic_tool_calls(blocks)

        assert len(parsed) == 1
        tc = parsed[0]
        assert isinstance(tc, ToolCall)
        assert tc.id == "toolu_01"
        assert tc.name == "compute_tax"
        assert tc.arguments == {"regime": "new", "income": 1_500_000}

    def test_parse_anthropic_mixed_content(self) -> None:
        """text + tool_use blocks -- only tool_use entries are returned."""
        blocks = [
            {"type": "text", "text": "Let me compute that for you."},
            {
                "type": "tool_use",
                "id": "toolu_02",
                "name": "search_sections",
                "input": {"query": "section 80D"},
            },
            {"type": "text", "text": "Here are the results."},
        ]
        parsed = parse_anthropic_tool_calls(blocks)

        assert len(parsed) == 1
        assert parsed[0].name == "search_sections"
        assert parsed[0].arguments == {"query": "section 80D"}

    def test_parse_anthropic_ignores_text_blocks(self) -> None:
        """A response containing only text blocks produces an empty list."""
        blocks = [
            {"type": "text", "text": "No tools needed here."},
            {"type": "text", "text": "Just a plain answer."},
        ]
        parsed = parse_anthropic_tool_calls(blocks)
        assert parsed == []


# ===================================================================
# Round-trip
# ===================================================================

class TestRoundTrip:
    """Verify that converting tools and then parsing a mock response yields
    correct ToolCall objects."""

    def test_openai_roundtrip(self, sample_tools: list[ToolDefinition]) -> None:
        """Convert tools -> build a mock OpenAI response -> parse -> verify ToolCall."""
        # 1. Convert definitions to OpenAI wire format
        wire_tools = to_openai_tools(sample_tools)

        # 2. Simulate the model choosing the first tool
        chosen = wire_tools[0]["function"]
        mock_arguments = {"regime": "new", "income": 900_000}
        mock_response_calls = [
            {
                "id": "call_rt_1",
                "function": {
                    "name": chosen["name"],
                    "arguments": json.dumps(mock_arguments),
                },
            },
        ]

        # 3. Parse the mock response
        parsed = parse_openai_tool_calls(mock_response_calls)

        assert len(parsed) == 1
        tc = parsed[0]
        assert tc.id == "call_rt_1"
        assert tc.name == sample_tools[0].name
        assert tc.arguments == mock_arguments
