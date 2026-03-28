"""Tests for kara_api.llm.client — LLMClient wrapper."""
from __future__ import annotations

import pytest

from kara_api.llm.client import SYSTEM_PROMPT, LLMClient
from kara_api.llm.models import (
    LLMResponse,
    Message,
    Role,
    StreamChunk,
    TokenUsage,
    ToolDefinition,
)
from kara_api.llm.providers import FakeLLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_msg(text: str = "Hello") -> Message:
    return Message(role=Role.user, content=text)


def _tool_def(name: str = "compute_tax") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Tool: {name}",
        parameters={"type": "object", "properties": {}},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMClient:
    """Unit tests for the LLMClient class."""

    async def test_chat_prepends_system_prompt(self):
        """The first message sent to the provider must be the system prompt."""
        provider = FakeLLMProvider()
        client = LLMClient(provider)

        await client.chat([_user_msg()])

        req = provider.last_request
        assert req is not None
        assert len(req.messages) == 2
        assert req.messages[0].role == Role.system
        assert req.messages[0].content == SYSTEM_PROMPT

    async def test_chat_forwards_tools(self):
        """Tool definitions are forwarded to the provider in the request."""
        provider = FakeLLMProvider()
        client = LLMClient(provider)
        tools = [_tool_def("compute_tax"), _tool_def("compare_regimes")]

        await client.chat([_user_msg()], tools=tools)

        req = provider.last_request
        assert req is not None
        assert len(req.tools) == 2
        assert req.tools[0].name == "compute_tax"
        assert req.tools[1].name == "compare_regimes"

    async def test_chat_returns_response(self):
        """chat() returns the LLMResponse produced by the provider."""
        canned = LLMResponse(
            content="Section 80C allows up to 1.5 lakh deduction.",
            model="fake",
            stop_reason="stop",
            usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )
        provider = FakeLLMProvider(responses=[canned])
        client = LLMClient(provider)

        result = await client.chat([_user_msg()])

        assert result.content == "Section 80C allows up to 1.5 lakh deduction."
        assert result.model == "fake"
        assert result.usage.total_tokens == 30

    async def test_chat_uses_custom_system_prompt(self):
        """A custom system prompt overrides the default."""
        custom = "You are a helpful test assistant."
        provider = FakeLLMProvider()
        client = LLMClient(provider, system_prompt=custom)

        await client.chat([_user_msg()])

        req = provider.last_request
        assert req is not None
        assert req.messages[0].content == custom

    async def test_chat_stream_yields_chunks(self):
        """chat_stream() must yield StreamChunk objects including a final chunk."""
        provider = FakeLLMProvider(default_content="hello world")
        client = LLMClient(provider)

        chunks: list[StreamChunk] = []
        async for chunk in client.chat_stream([_user_msg()]):
            chunks.append(chunk)

        # FakeLLMProvider splits on spaces -> 2 content chunks + 1 final
        assert len(chunks) == 3
        assert chunks[0].content == "hello "
        assert chunks[1].content == "world "
        assert chunks[2].is_final is True

    async def test_chat_default_temperature(self):
        """Default temperature is 0.3."""
        provider = FakeLLMProvider()
        client = LLMClient(provider)

        await client.chat([_user_msg()])

        req = provider.last_request
        assert req is not None
        assert req.temperature == pytest.approx(0.3)

    async def test_chat_custom_temperature(self):
        """Caller can override the temperature."""
        provider = FakeLLMProvider()
        client = LLMClient(provider)

        await client.chat([_user_msg()], temperature=0.9)

        req = provider.last_request
        assert req is not None
        assert req.temperature == pytest.approx(0.9)

    async def test_chat_passes_max_tokens(self):
        """max_tokens is forwarded to the provider request."""
        provider = FakeLLMProvider()
        client = LLMClient(provider)

        await client.chat([_user_msg()], max_tokens=2048)

        req = provider.last_request
        assert req is not None
        assert req.max_tokens == 2048
