"""Tests for kara_api.agent.loop — core agent conversation loop."""
from __future__ import annotations

import pytest

from kara_api.agent.loop import (
    _FALLBACK_MESSAGE,
    AgentError,
    AgentLoop,
    AgentResponse,
)
from kara_api.agent.profile_builder import ProfileBuilder
from kara_api.llm.client import LLMClient
from kara_api.llm.models import (
    LLMResponse,
    Message,
    Role,
    TokenUsage,
    ToolCall,
)
from kara_api.llm.providers import FakeLLMProvider
from kara_api.tools.executor import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_response(
    content: str = "Here is your answer.",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> LLMResponse:
    """Build an LLMResponse with only text (no tool calls)."""
    return LLMResponse(
        content=content,
        model="fake",
        stop_reason="stop",
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


def _tool_response(
    tool_calls: list[ToolCall],
    content: str | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> LLMResponse:
    """Build an LLMResponse that requests tool calls."""
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        model="fake",
        stop_reason="tool_calls",
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_provider():
    return FakeLLMProvider()


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def agent_loop(fake_provider, registry):
    client = LLMClient(fake_provider)
    return AgentLoop(llm_client=client, tool_registry=registry)


# ---------------------------------------------------------------------------
# Group 1: Simple text responses
# ---------------------------------------------------------------------------


class TestSimpleTextResponses:
    """Agent returns text without calling any tools."""

    async def test_simple_text_response(self, registry):
        """FakeLLMProvider returns text; verify content, iterations, empty tool_calls."""
        provider = FakeLLMProvider(responses=[_text_response("Hello, taxpayer!")])
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("Hi")

        assert result.content == "Hello, taxpayer!"
        assert result.iterations == 1
        assert result.tool_calls_made == []

    async def test_empty_history(self, agent_loop):
        """history=None works correctly (no crash, default empty)."""
        result = await agent_loop.run("Hello", history=None)

        assert isinstance(result, AgentResponse)
        assert result.iterations == 1

    async def test_with_prior_history(self, registry):
        """Passing existing messages in history includes them in the request."""
        provider = FakeLLMProvider(responses=[_text_response()])
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        history = [
            Message(role=Role.user, content="What is 80C?"),
            Message(role=Role.assistant, content="Section 80C allows..."),
        ]
        await loop.run("Tell me more", history=history)

        req = provider.last_request
        assert req is not None
        # system prompt + 2 history msgs + 1 new user msg = 4
        assert len(req.messages) == 4
        assert req.messages[1].content == "What is 80C?"
        assert req.messages[2].content == "Section 80C allows..."
        assert req.messages[3].content == "Tell me more"

    async def test_token_usage_tracked(self, registry):
        """total_usage reflects the provider's reported usage."""
        provider = FakeLLMProvider(
            responses=[_text_response(prompt_tokens=50, completion_tokens=30)]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("Compute my tax")

        assert result.total_usage.prompt_tokens == 50
        assert result.total_usage.completion_tokens == 30
        assert result.total_usage.total_tokens == 80


# ---------------------------------------------------------------------------
# Group 2: Single tool call then text
# ---------------------------------------------------------------------------


class TestSingleToolCall:
    """LLM requests one tool, gets result, then gives final answer."""

    async def test_single_tool_call_then_response(self, registry):
        """Provider returns tool_call then text. Verify iterations=2, 1 record."""
        tc = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "salary"},
        )
        provider = FakeLLMProvider(
            responses=[
                _tool_response([tc]),
                _text_response("TDS on salary is as per slab."),
            ]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("What is TDS on salary?")

        assert result.iterations == 2
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].tool_name == "get_tds_rate"
        assert result.content == "TDS on salary is as per slab."

    async def test_tool_result_in_history(self, registry):
        """Provider's second request includes the tool result message."""
        tc = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "rent"},
        )
        provider = FakeLLMProvider(
            responses=[_tool_response([tc]), _text_response()]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        await loop.run("TDS on rent?")

        req = provider.last_request
        assert req is not None
        # Find tool result message in the second request
        tool_msgs = [m for m in req.messages if m.role == Role.tool]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "call_1"
        assert "194I" in tool_msgs[0].content  # rent TDS section

    async def test_assistant_message_ordering(self, registry):
        """Assistant message with tool_calls precedes tool result messages."""
        tc = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "interest"},
        )
        provider = FakeLLMProvider(
            responses=[_tool_response([tc]), _text_response()]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        await loop.run("TDS on interest?")

        req = provider.last_request
        assert req is not None
        # Find the assistant msg with tool_calls and the following tool msg
        roles = [m.role for m in req.messages]
        # After system, user we should have assistant, tool
        assistant_idx = roles.index(Role.assistant)
        assert roles[assistant_idx + 1] == Role.tool


# ---------------------------------------------------------------------------
# Group 3: Multiple tool calls in a single response
# ---------------------------------------------------------------------------


class TestMultipleToolCalls:
    """LLM requests multiple tools at once."""

    async def test_multiple_tool_calls_single_response(self, registry):
        """LLM returns 2 tool_calls at once; both are executed."""
        tc1 = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "salary"},
        )
        tc2 = ToolCall(
            id="call_2",
            name="get_tds_rate",
            arguments={"payment_type": "rent"},
        )
        provider = FakeLLMProvider(
            responses=[_tool_response([tc1, tc2]), _text_response("Done.")]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("TDS rates?")

        assert result.iterations == 2
        assert len(result.tool_calls_made) == 2

    async def test_all_records_captured(self, registry):
        """All ToolCallRecords present with correct data."""
        tc1 = ToolCall(
            id="call_a",
            name="get_tds_rate",
            arguments={"payment_type": "salary"},
        )
        tc2 = ToolCall(
            id="call_b",
            name="get_tds_rate",
            arguments={"payment_type": "dividend"},
        )
        provider = FakeLLMProvider(
            responses=[_tool_response([tc1, tc2]), _text_response()]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("TDS info")

        names = [r.tool_name for r in result.tool_calls_made]
        assert names == ["get_tds_rate", "get_tds_rate"]
        assert all(not r.is_error for r in result.tool_calls_made)
        # Salary result should mention section 192
        assert "192" in result.tool_calls_made[0].result
        # Dividend result should mention section 194
        assert "194" in result.tool_calls_made[1].result


# ---------------------------------------------------------------------------
# Group 4: Multi-iteration tool calls
# ---------------------------------------------------------------------------


class TestMultiIteration:
    """LLM needs multiple rounds of tool calls before giving a final answer."""

    async def test_two_rounds_of_tool_calls(self, registry):
        """tool_call -> tool_call -> text gives iterations=3."""
        tc1 = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "salary"},
        )
        tc2 = ToolCall(
            id="call_2",
            name="get_tds_rate",
            arguments={"payment_type": "rent"},
        )
        provider = FakeLLMProvider(
            responses=[
                _tool_response([tc1]),
                _tool_response([tc2]),
                _text_response("Summary of TDS rates."),
            ]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("All TDS?")

        assert result.iterations == 3
        assert len(result.tool_calls_made) == 2
        assert result.content == "Summary of TDS rates."

    async def test_usage_accumulated_across_iterations(self, registry):
        """total usage sums across all LLM calls."""
        tc = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "salary"},
        )
        provider = FakeLLMProvider(
            responses=[
                _tool_response([tc], prompt_tokens=100, completion_tokens=20),
                _text_response(prompt_tokens=200, completion_tokens=40),
            ]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("TDS on salary")

        assert result.total_usage.prompt_tokens == 300
        assert result.total_usage.completion_tokens == 60
        assert result.total_usage.total_tokens == 360


# ---------------------------------------------------------------------------
# Group 5: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Edge cases and error paths."""

    async def test_max_iterations_guard(self, registry):
        """Provider always returns tool_calls; loop stops at max_iterations with fallback."""
        # Create a provider that always returns a tool call
        responses = [
            _tool_response(
                [ToolCall(id=f"call_{i}", name="get_tds_rate",
                          arguments={"payment_type": "salary"})]
            )
            for i in range(15)
        ]
        provider = FakeLLMProvider(responses=responses)
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry, max_iterations=10)

        result = await loop.run("Infinite loop?")

        assert result.iterations == 10
        assert result.content == _FALLBACK_MESSAGE

    async def test_max_iterations_custom(self, registry):
        """Set max_iterations=2; verify loop stops at 2."""
        responses = [
            _tool_response(
                [ToolCall(id=f"call_{i}", name="get_tds_rate",
                          arguments={"payment_type": "salary"})]
            )
            for i in range(5)
        ]
        provider = FakeLLMProvider(responses=responses)
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry, max_iterations=2)

        result = await loop.run("Still looping?")

        assert result.iterations == 2
        assert result.content == _FALLBACK_MESSAGE

    async def test_tool_error_sent_to_llm(self, registry):
        """Unknown tool produces error content that is passed back as tool result."""
        tc = ToolCall(
            id="call_bad",
            name="nonexistent_tool",
            arguments={"foo": "bar"},
        )
        provider = FakeLLMProvider(
            responses=[_tool_response([tc]), _text_response("I recovered.")]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("Do something weird")

        assert result.iterations == 2
        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made[0].is_error is True
        assert "Unknown tool" in result.tool_calls_made[0].result
        # The LLM got the error and self-corrected with a text response
        assert result.content == "I recovered."

    async def test_llm_error_raises_agent_error(self, registry):
        """If the provider raises, AgentError is raised with iterations/usage."""

        class ExplodingProvider:
            async def complete(self, request):
                raise RuntimeError("Provider exploded")

            async def stream(self, request):
                raise RuntimeError("Provider exploded")
                yield  # unreachable — makes this an async generator

        client = LLMClient(ExplodingProvider())
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        with pytest.raises(AgentError, match="Provider exploded") as exc_info:
            await loop.run("Boom")

        assert exc_info.value.iterations == 0
        assert exc_info.value.usage.total_tokens == 0


# ---------------------------------------------------------------------------
# Group 6: ProfileBuilder integration
# ---------------------------------------------------------------------------


class TestProfileBuilder:
    """Profile state is correctly threaded through the loop."""

    async def test_profile_passed_through(self, registry):
        """Pass ProfileBuilder with slots; verify snapshot in response."""
        provider = FakeLLMProvider(responses=[_text_response()])
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        profile = ProfileBuilder(initial_slots={"gross_salary": 1500000, "regime": "new"})
        result = await loop.run("Compute tax", profile=profile)

        assert result.profile_snapshot == {
            "slots": {"gross_salary": 1500000, "regime": "new"}
        }

    async def test_default_profile_when_none(self, registry):
        """profile=None gives empty snapshot."""
        provider = FakeLLMProvider(responses=[_text_response()])
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("Hello", profile=None)

        assert result.profile_snapshot == {"slots": {}}

    async def test_profile_survives_tool_calls(self, registry):
        """Profile state persists through iterations with tool calls."""
        tc = ToolCall(
            id="call_1",
            name="get_tds_rate",
            arguments={"payment_type": "salary"},
        )
        provider = FakeLLMProvider(
            responses=[_tool_response([tc]), _text_response()]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        profile = ProfileBuilder(initial_slots={"age_category": "senior"})
        result = await loop.run("Tax info", profile=profile)

        assert result.profile_snapshot == {"slots": {"age_category": "senior"}}
        assert result.iterations == 2


# ---------------------------------------------------------------------------
# Group 7: End-to-end integration with real tool execution
# ---------------------------------------------------------------------------


class TestCustomTools:
    """Verify the tools parameter on AgentLoop is forwarded to the LLM."""

    async def test_custom_tools_forwarded(self, registry):
        """When tools= is passed, only those tools are sent to the provider."""
        from kara_api.llm.models import ToolDefinition

        custom_tool = ToolDefinition(
            name="custom_tool",
            description="A custom test tool",
            parameters={"type": "object", "properties": {}},
        )
        provider = FakeLLMProvider(responses=[_text_response()])
        client = LLMClient(provider)
        loop = AgentLoop(
            llm_client=client, tool_registry=registry, tools=[custom_tool]
        )

        await loop.run("Test custom tools")

        req = provider.last_request
        assert req is not None
        assert len(req.tools) == 1
        assert req.tools[0].name == "custom_tool"


class TestIntegration:
    """Full loop with real ToolRegistry execution."""

    async def test_compute_tax_end_to_end(self, registry):
        """FakeLLMProvider returns compute_tax tool_call; ToolRegistry runs for real."""
        tc = ToolCall(
            id="call_tax",
            name="compute_tax",
            arguments={"gross_salary": 1500000, "regime": "new"},
        )
        provider = FakeLLMProvider(
            responses=[
                _tool_response([tc]),
                _text_response("Your tax is Rs 1,12,500 under new regime."),
            ]
        )
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=registry)

        result = await loop.run("Compute my tax on 15 lakh salary, new regime")

        assert result.iterations == 2
        assert len(result.tool_calls_made) == 1

        record = result.tool_calls_made[0]
        assert record.tool_name == "compute_tax"
        assert record.is_error is False
        # The real tax engine produces JSON with tax data
        assert "total_tax" in record.result
        assert result.content == "Your tax is Rs 1,12,500 under new regime."


# ---------------------------------------------------------------------------
# Streaming agent loop
# ---------------------------------------------------------------------------


class TestRunStream:
    """AgentLoop.run_stream yields typed events: content_delta as tokens
    arrive, tool_result after each tool execution, done with the final
    AgentResponse."""

    def _make_loop(self, responses: list[LLMResponse]) -> AgentLoop:
        provider = FakeLLMProvider(responses=responses)
        client = LLMClient(provider)
        return AgentLoop(llm_client=client, tool_registry=ToolRegistry())

    @pytest.mark.asyncio
    async def test_streams_content_deltas_for_text_answer(self):
        loop = self._make_loop([_text_response("Hello there friend")])

        events = [e async for e in loop.run_stream("hi")]

        deltas = [e for e in events if e.type == "content_delta"]
        assert len(deltas) == 3  # FakeLLMProvider streams word by word
        assert "".join(d.text for d in deltas).strip() == "Hello there friend"

        done = [e for e in events if e.type == "done"]
        assert len(done) == 1
        assert done[0] is events[-1]
        assert done[0].response.content.strip() == "Hello there friend"
        assert done[0].response.iterations == 1

    @pytest.mark.asyncio
    async def test_tool_call_turn_then_final_answer(self):
        tc = ToolCall(id="t1", name="compute_tax", arguments={"gross_salary": 1500000})
        loop = self._make_loop(
            [
                _tool_response([tc]),
                _text_response("Your tax is computed."),
            ]
        )

        events = [e async for e in loop.run_stream("tax on 15L?")]

        tool_events = [e for e in events if e.type == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0].record.tool_name == "compute_tax"
        assert tool_events[0].record.is_error is False

        # Tool event must come before the final answer's deltas
        types = [e.type for e in events]
        assert types.index("tool_result") < types.index("content_delta")

        done = events[-1]
        assert done.type == "done"
        assert done.response.iterations == 2
        assert len(done.response.tool_calls_made) == 1
        assert done.response.content.strip() == "Your tax is computed."

    @pytest.mark.asyncio
    async def test_max_iterations_yields_fallback(self):
        tc = ToolCall(id="t1", name="get_tds_rate", arguments={"payment_type": "rent"})
        responses = [_tool_response([tc]) for _ in range(12)]
        provider = FakeLLMProvider(responses=responses)
        client = LLMClient(provider)
        loop = AgentLoop(llm_client=client, tool_registry=ToolRegistry(), max_iterations=2)

        events = [e async for e in loop.run_stream("loop forever")]

        done = events[-1]
        assert done.type == "done"
        assert _FALLBACK_MESSAGE in done.response.content
        # The fallback must also have been streamed so the client displays it
        deltas = "".join(e.text for e in events if e.type == "content_delta")
        assert _FALLBACK_MESSAGE.split()[0] in deltas

    @pytest.mark.asyncio
    async def test_provider_error_raises_agent_error(self):
        class ExplodingProvider:
            async def complete(self, request):
                raise RuntimeError("Provider exploded")

            async def stream(self, request):
                raise RuntimeError("Provider exploded")
                yield  # unreachable — makes this an async generator

        client = LLMClient(ExplodingProvider())
        loop = AgentLoop(llm_client=client, tool_registry=ToolRegistry())

        with pytest.raises(AgentError):
            async for _ in loop.run_stream("boom"):
                pass

    @pytest.mark.asyncio
    async def test_usage_accumulated_across_turns(self):
        tc = ToolCall(id="t1", name="get_tds_rate", arguments={"payment_type": "rent"})
        loop = self._make_loop(
            [
                _tool_response([tc], prompt_tokens=100, completion_tokens=20),
                _text_response("done", prompt_tokens=10, completion_tokens=5),
            ]
        )

        events = [e async for e in loop.run_stream("tds on rent")]
        usage = events[-1].response.total_usage
        assert usage.prompt_tokens == 110
        assert usage.completion_tokens == 25
