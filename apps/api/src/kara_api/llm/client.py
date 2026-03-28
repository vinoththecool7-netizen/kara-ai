"""High-level LLM client for Kara agent use."""
from __future__ import annotations

from collections.abc import AsyncIterator

from kara_api.llm.models import (
    LLMRequest,
    LLMResponse,
    Message,
    Role,
    StreamChunk,
    ToolDefinition,
)
from kara_api.llm.providers import LLMProvider

SYSTEM_PROMPT = (
    "You are Kara, an AI tax advisor specializing in Indian income tax. "
    "You help taxpayers understand their obligations under the Income Tax Act, "
    "compute taxes, compare regimes, find deductions, and answer tax law questions. "
    "Always cite relevant sections. Use the provided tools for calculations. "
    "Never give investment advice. Clarify ambiguous queries before computing."
)


class LLMClient:
    """Stateless LLM client that wraps a provider."""

    def __init__(self, provider: LLMProvider, system_prompt: str = SYSTEM_PROMPT):
        self.provider = provider
        self.system_prompt = system_prompt

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a non-streaming chat request. Prepends system prompt."""
        all_messages = [Message(role=Role.system, content=self.system_prompt), *messages]
        request = LLMRequest(
            messages=all_messages,
            tools=tools or [],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        return await self.provider.complete(request)

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming chat request. Prepends system prompt."""
        all_messages = [Message(role=Role.system, content=self.system_prompt), *messages]
        request = LLMRequest(
            messages=all_messages,
            tools=tools or [],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in self.provider.stream(request):
            yield chunk
