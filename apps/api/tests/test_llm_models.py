"""Tests for the unified LLM data models."""
from kara_api.llm.models import (
    LLMRequest,
    LLMResponse,
    Message,
    Role,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class TestMessage:
    def test_user_message_defaults(self):
        msg = Message(role=Role.user, content="Hello")
        assert msg.role == Role.user
        assert msg.content == "Hello"
        assert msg.tool_calls == []
        assert msg.tool_call_id is None

    def test_assistant_message_with_tool_calls(self):
        tc = ToolCall(id="call_1", name="get_section", arguments={"section": "80C"})
        msg = Message(role=Role.assistant, content=None, tool_calls=[tc])
        assert msg.role == Role.assistant
        assert msg.content is None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "get_section"

    def test_tool_result_message(self):
        msg = Message(role=Role.tool, content='{"result": "ok"}', tool_call_id="call_1")
        assert msg.role == Role.tool
        assert msg.tool_call_id == "call_1"
        assert msg.content is not None


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------

class TestToolCall:
    def test_arguments_is_dict(self):
        tc = ToolCall(id="call_42", name="compute_tax", arguments={"income": 1_200_000})
        assert isinstance(tc.arguments, dict)
        assert tc.arguments["income"] == 1_200_000


# ---------------------------------------------------------------------------
# ToolDefinition
# ---------------------------------------------------------------------------

class TestToolDefinition:
    def test_has_json_schema_parameters(self):
        schema = {
            "type": "object",
            "properties": {
                "income": {"type": "number", "description": "Annual income in INR"},
            },
            "required": ["income"],
        }
        td = ToolDefinition(
            name="compute_tax",
            description="Compute income tax for a given income",
            parameters=schema,
        )
        assert td.parameters["type"] == "object"
        assert "income" in td.parameters["properties"]


# ---------------------------------------------------------------------------
# LLMRequest
# ---------------------------------------------------------------------------

class TestLLMRequest:
    def test_defaults(self):
        msg = Message(role=Role.user, content="Hi")
        req = LLMRequest(messages=[msg])
        assert req.temperature == 0.3
        assert req.max_tokens == 4096
        assert req.stream is False
        assert req.tools == []
        assert len(req.messages) == 1

    def test_with_tools(self):
        msg = Message(role=Role.user, content="What deductions can I claim?")
        tool = ToolDefinition(
            name="search_sections",
            description="Search tax sections",
            parameters={"type": "object", "properties": {}},
        )
        req = LLMRequest(messages=[msg], tools=[tool], temperature=0.7)
        assert len(req.tools) == 1
        assert req.tools[0].name == "search_sections"
        assert req.temperature == 0.7


# ---------------------------------------------------------------------------
# LLMResponse
# ---------------------------------------------------------------------------

class TestLLMResponse:
    def test_text_response(self):
        resp = LLMResponse(
            content="Section 80C allows deductions up to 1.5 lakh.",
            model="gpt-4o-mini",
            stop_reason="stop",
        )
        assert resp.content is not None
        assert resp.tool_calls == []
        assert resp.model == "gpt-4o-mini"
        assert resp.usage.total_tokens == 0

    def test_tool_use_response(self):
        tc = ToolCall(id="call_abc", name="get_section", arguments={"id": "80C"})
        resp = LLMResponse(
            tool_calls=[tc],
            model="claude-sonnet-4-20250514",
            stop_reason="tool_use",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
        )
        assert resp.content is None
        assert len(resp.tool_calls) == 1
        assert resp.stop_reason == "tool_use"
        assert resp.usage.total_tokens == 125

    def test_mixed_response(self):
        tc = ToolCall(id="call_xyz", name="compute_tax", arguments={"income": 800_000})
        resp = LLMResponse(
            content="Let me calculate that for you.",
            tool_calls=[tc],
            model="gpt-4o",
            stop_reason="tool_use",
        )
        assert resp.content is not None
        assert len(resp.tool_calls) == 1


# ---------------------------------------------------------------------------
# StreamChunk
# ---------------------------------------------------------------------------

class TestStreamChunk:
    def test_content_chunk(self):
        chunk = StreamChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.is_final is False
        assert chunk.usage is None
        assert chunk.tool_calls == []

    def test_final_chunk_with_usage(self):
        usage = TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60)
        chunk = StreamChunk(is_final=True, usage=usage)
        assert chunk.is_final is True
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 60
        assert chunk.content is None
