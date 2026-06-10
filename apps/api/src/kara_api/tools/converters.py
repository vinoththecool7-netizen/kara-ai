"""Stateless converters between internal ToolDefinition/ToolCall format and
provider-specific wire formats (OpenAI and Anthropic).

Each function is a pure mapping -- no I/O, no side-effects, no provider SDK
dependency.
"""
from __future__ import annotations

import json
from typing import Any

from kara_api.llm.models import ToolCall, ToolDefinition

# ---------------------------------------------------------------------------
# Internal -> Provider wire format
# ---------------------------------------------------------------------------

def to_openai_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert ToolDefinitions to OpenAI function-calling format.

    Returns a list of dicts, each shaped as::

        {
            "type": "function",
            "function": {
                "name": ...,
                "description": ...,
                "parameters": ...   # JSON Schema object
            }
        }
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def to_anthropic_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert ToolDefinitions to Anthropic tool format.

    Returns a list of dicts, each shaped as::

        {
            "name": ...,
            "description": ...,
            "input_schema": ...   # JSON Schema object
        }

    Note: Anthropic uses ``input_schema`` instead of ``parameters``.
    """
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


# ---------------------------------------------------------------------------
# Provider wire format -> Internal
# ---------------------------------------------------------------------------

def parse_openai_tool_calls(tool_calls_data: list[dict]) -> list[ToolCall]:
    """Parse an OpenAI ``tool_calls`` array from a chat-completion response.

    Expected input element format::

        {
            "id": "call_abc",
            "function": {
                "name": "...",
                "arguments": '{"key": "val"}'   # JSON *string*
            }
        }

    OpenAI sends ``arguments`` as a JSON **string** that needs to be parsed
    into a dict.
    """
    result: list[ToolCall] = []
    for tc in tool_calls_data:
        fn = tc["function"]
        arguments_raw = fn["arguments"]
        if isinstance(arguments_raw, str):
            arguments = json.loads(arguments_raw)
        else:
            # Defensive: if somehow already a dict, accept it.
            arguments = arguments_raw
        result.append(
            ToolCall(
                id=tc["id"],
                name=fn["name"],
                arguments=arguments,
            )
        )
    return result


def parse_anthropic_tool_calls(content_blocks: list[dict]) -> list[ToolCall]:
    """Parse Anthropic content blocks to extract ``tool_use`` entries.

    Expected input format (a list of heterogeneous content blocks)::

        [
            {"type": "text", "text": "..."},
            {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
        ]

    Anthropic sends ``input`` as an already-parsed **dict** (not a JSON
    string).  Only blocks where ``type == "tool_use"`` are extracted.
    """
    return [
        ToolCall(
            id=block["id"],
            name=block["name"],
            arguments=block["input"],
        )
        for block in content_blocks
        if block.get("type") == "tool_use"
    ]
