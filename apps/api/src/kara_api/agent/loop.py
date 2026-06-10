"""Core agent conversation loop: LLM <-> tool execution <-> user.

Orchestrates the iterative cycle of sending messages to the LLM,
executing any requested tool calls, feeding results back, and
repeating until the LLM produces a final text response or the
iteration budget is exhausted.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel

from kara_api.agent.profile_builder import ProfileBuilder
from kara_api.llm.client import LLMClient
from kara_api.llm.models import (
    LLMResponse,
    Message,
    Role,
    TokenUsage,
    ToolDefinition,
)
from kara_api.tools.executor import ToolRegistry
from kara_api.tools.schemas import ALL_TOOLS

logger = logging.getLogger(__name__)

_FALLBACK_MESSAGE = (
    "I'm sorry, I wasn't able to complete your request within the allowed "
    "number of steps. Could you try rephrasing or simplifying your question?"
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ToolCallRecord(BaseModel):
    """Record of a single tool invocation for observability."""

    tool_name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool


class AgentResponse(BaseModel):
    """Complete result from one agent turn."""

    content: str
    tool_calls_made: list[ToolCallRecord]
    total_usage: TokenUsage
    iterations: int
    profile_snapshot: dict[str, Any]


class AgentError(Exception):
    """Raised when the agent loop encounters an unrecoverable error."""

    def __init__(self, message: str, iterations: int, usage: TokenUsage):
        super().__init__(message)
        self.iterations = iterations
        self.usage = usage


class AgentStreamEvent(BaseModel):
    """A single event emitted by :meth:`AgentLoop.run_stream`.

    - ``content_delta``: ``text`` holds the next token(s) of assistant text.
    - ``tool_result``: ``record`` holds the completed tool invocation.
    - ``done``: ``response`` holds the final AgentResponse; always the last event.
    """

    type: Literal["content_delta", "tool_result", "done"]
    text: str = ""
    record: ToolCallRecord | None = None
    response: AgentResponse | None = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _accumulate_usage(total: TokenUsage, delta: TokenUsage) -> TokenUsage:
    """Return a new TokenUsage summing *total* and *delta*."""
    return TokenUsage(
        prompt_tokens=total.prompt_tokens + delta.prompt_tokens,
        completion_tokens=total.completion_tokens + delta.completion_tokens,
        total_tokens=total.total_tokens + delta.total_tokens,
    )


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


class AgentLoop:
    """Core conversation loop: LLM <-> tools <-> user.

    Stateless per-request.  Session state (history, profile) is passed
    in and returned so that callers own the persistence strategy.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        *,
        max_iterations: int = 10,
        tools: list[ToolDefinition] | None = None,
    ):
        self._llm = llm_client
        self._registry = tool_registry
        self._max_iterations = max_iterations
        self._tools = tools if tools is not None else ALL_TOOLS

    async def run(
        self,
        user_message: str,
        history: list[Message] | None = None,
        profile: ProfileBuilder | None = None,
    ) -> AgentResponse:
        """Execute one full agent turn (may involve multiple LLM round-trips).

        Parameters
        ----------
        user_message:
            The latest user utterance.
        history:
            Prior conversation messages (excluding *user_message*).
        profile:
            Accumulated taxpayer profile; a fresh one is created if ``None``.

        Returns
        -------
        AgentResponse
            The final text reply, tool-call records, token usage, and a
            snapshot of the profile state.

        Raises
        ------
        AgentError
            If the LLM provider raises an unexpected exception.
        """
        messages = list(history or []) + [
            Message(role=Role.user, content=user_message),
        ]
        profile = profile or ProfileBuilder()

        total_usage = TokenUsage()
        tool_call_records: list[ToolCallRecord] = []
        iterations = 0
        content = ""

        while iterations < self._max_iterations:
            # ----- call the LLM ------------------------------------------
            try:
                response: LLMResponse = await self._llm.chat(
                    messages, tools=self._tools
                )
            except Exception as exc:
                raise AgentError(
                    str(exc), iterations=iterations, usage=total_usage
                ) from exc

            total_usage = _accumulate_usage(total_usage, response.usage)
            iterations += 1

            # ----- tool calls? -------------------------------------------
            if response.tool_calls:
                # Append assistant message (content + tool_calls)
                messages.append(
                    Message(
                        role=Role.assistant,
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                # Execute each tool and append result messages
                for tc in response.tool_calls:
                    result = await self._registry.execute(tc)
                    messages.append(
                        Message(
                            role=Role.tool,
                            content=result.content,
                            tool_call_id=result.tool_call_id,
                        )
                    )
                    tool_call_records.append(
                        ToolCallRecord(
                            tool_name=tc.name,
                            arguments=tc.arguments,
                            result=result.content,
                            is_error=result.is_error,
                        )
                    )

                continue  # loop back for the LLM to process tool results

            # ----- final text answer -------------------------------------
            content = response.content or ""
            break
        else:
            # max iterations exhausted while still getting tool_calls
            content = _FALLBACK_MESSAGE

        return AgentResponse(
            content=content,
            tool_calls_made=tool_call_records,
            total_usage=total_usage,
            iterations=iterations,
            profile_snapshot=profile.to_dict(),
        )

    async def run_stream(
        self,
        user_message: str,
        history: list[Message] | None = None,
        profile: ProfileBuilder | None = None,
    ) -> AsyncIterator[AgentStreamEvent]:
        """Execute one agent turn, streaming events as they happen.

        Yields ``content_delta`` events as assistant text arrives token by
        token, a ``tool_result`` event after each tool execution, and finally
        a single ``done`` event carrying the complete :class:`AgentResponse`.

        Raises
        ------
        AgentError
            If the LLM provider raises an unexpected exception.
        """
        messages = list(history or []) + [
            Message(role=Role.user, content=user_message),
        ]
        profile = profile or ProfileBuilder()

        total_usage = TokenUsage()
        tool_call_records: list[ToolCallRecord] = []
        iterations = 0
        content_parts: list[str] = []

        while iterations < self._max_iterations:
            turn_content = ""
            turn_tool_calls = []

            # ----- stream one LLM turn ------------------------------------
            try:
                async for chunk in self._llm.chat_stream(messages, tools=self._tools):
                    if chunk.content:
                        turn_content += chunk.content
                        yield AgentStreamEvent(type="content_delta", text=chunk.content)
                    if chunk.tool_calls:
                        turn_tool_calls.extend(chunk.tool_calls)
                    if chunk.usage:
                        total_usage = _accumulate_usage(total_usage, chunk.usage)
            except Exception as exc:
                raise AgentError(
                    str(exc), iterations=iterations, usage=total_usage
                ) from exc

            iterations += 1
            if turn_content:
                content_parts.append(turn_content)

            # ----- tool calls? -------------------------------------------
            if turn_tool_calls:
                messages.append(
                    Message(
                        role=Role.assistant,
                        content=turn_content or None,
                        tool_calls=turn_tool_calls,
                    )
                )
                for tc in turn_tool_calls:
                    result = await self._registry.execute(tc)
                    messages.append(
                        Message(
                            role=Role.tool,
                            content=result.content,
                            tool_call_id=result.tool_call_id,
                        )
                    )
                    record = ToolCallRecord(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        result=result.content,
                        is_error=result.is_error,
                    )
                    tool_call_records.append(record)
                    yield AgentStreamEvent(type="tool_result", record=record)

                continue  # loop back for the LLM to process tool results

            break  # final text answer (already streamed)
        else:
            # max iterations exhausted while still getting tool_calls —
            # stream the fallback so the client actually displays it.
            content_parts.append(_FALLBACK_MESSAGE)
            yield AgentStreamEvent(type="content_delta", text=_FALLBACK_MESSAGE)

        yield AgentStreamEvent(
            type="done",
            response=AgentResponse(
                # Everything the user saw, in order (text may have been
                # produced both before tool calls and as the final answer).
                content="\n\n".join(p for p in content_parts if p.strip()),
                tool_calls_made=tool_call_records,
                total_usage=total_usage,
                iterations=iterations,
                profile_snapshot=profile.to_dict(),
            ),
        )
