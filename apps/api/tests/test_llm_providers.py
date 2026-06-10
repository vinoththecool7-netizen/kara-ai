"""Tests for LLM provider abstraction layer.

Covers OpenAI, Anthropic, Ollama, Fake providers and the factory function.
All HTTP calls are mocked -- no real network I/O.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from kara_api.config import Settings
from kara_api.llm.models import (
    LLMRequest,
    LLMResponse,
    Message,
    Role,
    ToolCall,
    ToolDefinition,
)
from kara_api.llm.providers import (
    AnthropicProvider,
    FakeLLMProvider,
    OllamaProvider,
    OpenAIProvider,
    get_llm_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_request(content: str = "Hello") -> LLMRequest:
    return LLMRequest(messages=[Message(role=Role.user, content=content)])


def _request_with_system() -> LLMRequest:
    return LLMRequest(
        messages=[
            Message(role=Role.system, content="You are helpful."),
            Message(role=Role.user, content="Hello"),
        ]
    )


def _request_with_tools() -> LLMRequest:
    return LLMRequest(
        messages=[Message(role=Role.user, content="Compute my tax")],
        tools=[
            ToolDefinition(
                name="compute_tax",
                description="Compute income tax",
                parameters={
                    "type": "object",
                    "properties": {"income": {"type": "number"}},
                },
            )
        ],
    )


def _request_with_tool_result() -> LLMRequest:
    return LLMRequest(
        messages=[
            Message(role=Role.user, content="Compute my tax"),
            Message(
                role=Role.assistant,
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="compute_tax", arguments={"income": 1000000})
                ],
            ),
            Message(
                role=Role.tool,
                content='{"tax": 100000}',
                tool_call_id="call_1",
            ),
        ]
    )


def _openai_text_response() -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hello there!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "model": "gpt-4o",
    }


def _openai_tool_response() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "compute_tax",
                                "arguments": '{"income": 1000000}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        "model": "gpt-4o",
    }


def _openai_mixed_response() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Let me compute that.",
                    "tool_calls": [
                        {
                            "id": "call_xyz",
                            "type": "function",
                            "function": {
                                "name": "compute_tax",
                                "arguments": '{"income": 500000}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
        "model": "gpt-4o",
    }


def _anthropic_text_response() -> dict:
    return {
        "content": [{"type": "text", "text": "Hello from Claude!"}],
        "usage": {"input_tokens": 12, "output_tokens": 6},
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "end_turn",
    }


def _anthropic_tool_response() -> dict:
    return {
        "content": [
            {"type": "tool_use", "id": "toolu_1", "name": "compute_tax", "input": {"income": 800000}},
        ],
        "usage": {"input_tokens": 20, "output_tokens": 15},
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "tool_use",
    }


def _mock_httpx_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.request = MagicMock()
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=resp.request,
            response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# OpenAI Provider Tests
# ---------------------------------------------------------------------------


class TestOpenAIPayload:
    def test_basic_payload_structure(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        request = _simple_request()
        payload = provider._build_payload(request)

        assert payload["model"] == "gpt-4o"
        assert payload["temperature"] == 0.3
        assert payload["max_tokens"] == 4096
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Hello"
        assert "tools" not in payload

    def test_payload_includes_tools(self):
        provider = OpenAIProvider(api_key="sk-test")
        request = _request_with_tools()
        payload = provider._build_payload(request)

        assert "tools" in payload
        assert len(payload["tools"]) == 1
        assert payload["tools"][0]["type"] == "function"
        assert payload["tools"][0]["function"]["name"] == "compute_tax"

    def test_system_message_stays_in_messages(self):
        """OpenAI keeps system messages in the messages array."""
        provider = OpenAIProvider(api_key="sk-test")
        request = _request_with_system()
        payload = provider._build_payload(request)

        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are helpful."

    def test_tool_result_message_includes_tool_call_id(self):
        provider = OpenAIProvider(api_key="sk-test")
        request = _request_with_tool_result()
        payload = provider._build_payload(request)

        # Find the tool result message
        tool_msg = [m for m in payload["messages"] if m["role"] == "tool"]
        assert len(tool_msg) == 1
        assert tool_msg[0]["tool_call_id"] == "call_1"
        assert tool_msg[0]["content"] == '{"tax": 100000}'

    def test_assistant_message_with_tool_calls(self):
        provider = OpenAIProvider(api_key="sk-test")
        request = _request_with_tool_result()
        payload = provider._build_payload(request)

        assistant_msg = [m for m in payload["messages"] if m["role"] == "assistant"]
        assert len(assistant_msg) == 1
        assert "tool_calls" in assistant_msg[0]
        tc = assistant_msg[0]["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "compute_tax"
        assert json.loads(tc["function"]["arguments"]) == {"income": 1000000}


class TestOpenAIComplete:
    async def test_auth_header(self):
        provider = OpenAIProvider(api_key="sk-secret-key")
        mock_resp = _mock_httpx_response(200, _openai_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.complete(_simple_request())

            _, kwargs = mock_client.post.call_args
            assert kwargs["headers"]["Authorization"] == "Bearer sk-secret-key"

    async def test_parse_text_response(self):
        provider = OpenAIProvider(api_key="sk-test")
        mock_resp = _mock_httpx_response(200, _openai_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Hello there!"
        assert result.tool_calls == []
        assert result.stop_reason == "stop"
        assert result.model == "gpt-4o"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5
        assert result.usage.total_tokens == 15

    async def test_parse_tool_response(self):
        provider = OpenAIProvider(api_key="sk-test")
        mock_resp = _mock_httpx_response(200, _openai_tool_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_abc"
        assert result.tool_calls[0].name == "compute_tax"
        assert result.tool_calls[0].arguments == {"income": 1000000}
        assert result.stop_reason == "tool_calls"

    async def test_parse_mixed_response(self):
        provider = OpenAIProvider(api_key="sk-test")
        mock_resp = _mock_httpx_response(200, _openai_mixed_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Let me compute that."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "compute_tax"

    async def test_retry_on_429(self):
        provider = OpenAIProvider(api_key="sk-test")
        resp_429 = _mock_httpx_response(429)
        resp_429.raise_for_status = MagicMock()  # don't raise; we raise manually
        resp_ok = _mock_httpx_response(200, _openai_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls, \
             patch("kara_api.llm.providers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [resp_429, resp_ok]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Hello there!"
        mock_sleep.assert_called_once_with(1)  # 2**0 = 1

    async def test_retry_on_500(self):
        provider = OpenAIProvider(api_key="sk-test")
        resp_500 = _mock_httpx_response(500)
        resp_500.raise_for_status = MagicMock()
        resp_ok = _mock_httpx_response(200, _openai_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls, \
             patch("kara_api.llm.providers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [resp_500, resp_ok]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Hello there!"
        mock_sleep.assert_called_once_with(1)

    async def test_no_retry_on_401(self):
        provider = OpenAIProvider(api_key="sk-bad")
        resp_401 = _mock_httpx_response(401)

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = resp_401
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete(_simple_request())

        # Should only be called once (no retries)
        assert mock_client.post.call_count == 1

    async def test_max_retries_exhausted(self):
        provider = OpenAIProvider(api_key="sk-test")
        resp_429 = _mock_httpx_response(429)
        resp_429.raise_for_status = MagicMock()

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls, \
             patch("kara_api.llm.providers.asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.post.return_value = resp_429
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete(_simple_request())

        # 3 attempts total
        assert mock_client.post.call_count == 3


def _make_stream_context(mock_resp):
    """Create a synchronous context manager mock for httpx client.stream().

    httpx's client.stream() returns a context manager (not a coroutine), so
    we must NOT use AsyncMock for the .stream attribute itself.  Instead we
    return a MagicMock whose __aenter__/__aexit__ are async.
    """
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestOpenAIStream:
    async def test_streaming_text_chunks(self):
        provider = OpenAIProvider(api_key="sk-test")

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
            'data: {"choices":[{"delta":{"content":" world"}}]}\n',
            'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}\n',
            "data: [DONE]\n",
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp.aiter_lines = fake_aiter_lines

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=_make_stream_context(mock_resp))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(_simple_request()):
                chunks.append(chunk)

        assert len(chunks) == 4
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " world"
        # Third chunk has usage
        assert chunks[2].usage is not None
        assert chunks[2].usage.total_tokens == 7
        # Final chunk
        assert chunks[3].is_final is True

    async def test_streaming_ignores_empty_lines(self):
        provider = OpenAIProvider(api_key="sk-test")

        sse_lines = [
            "\n",
            "  \n",
            ": comment\n",
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n',
            "data: [DONE]\n",
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp.aiter_lines = fake_aiter_lines

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=_make_stream_context(mock_resp))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(_simple_request()):
                chunks.append(chunk)

        # Only "Hi" content chunk + final
        assert len(chunks) == 2
        assert chunks[0].content == "Hi"
        assert chunks[1].is_final is True


# ---------------------------------------------------------------------------
# Anthropic Provider Tests
# ---------------------------------------------------------------------------


class TestAnthropicPayload:
    def test_system_extracted_to_top_level(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        request = _request_with_system()
        payload = provider._build_payload(request)

        assert payload["system"] == "You are helpful."
        # System message should NOT be in the messages array
        roles = [m["role"] for m in payload["messages"]]
        assert "system" not in roles
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    def test_no_system_field_when_no_system_message(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        request = _simple_request()
        payload = provider._build_payload(request)

        assert "system" not in payload

    def test_tool_result_converted_to_user_content_block(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        request = _request_with_tool_result()
        payload = provider._build_payload(request)

        # The tool result should be a user message with content blocks
        user_msgs = [m for m in payload["messages"] if m["role"] == "user"]
        # Original user + tool result as user
        assert len(user_msgs) == 2
        tool_result_msg = user_msgs[1]
        assert isinstance(tool_result_msg["content"], list)
        block = tool_result_msg["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "call_1"

    def test_tools_use_anthropic_format(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        request = _request_with_tools()
        payload = provider._build_payload(request)

        assert "tools" in payload
        assert len(payload["tools"]) == 1
        tool = payload["tools"][0]
        assert "input_schema" in tool
        assert tool["name"] == "compute_tax"
        # Should NOT have "type": "function" wrapper like OpenAI
        assert "type" not in tool


class TestAnthropicComplete:
    async def test_headers(self):
        provider = AnthropicProvider(api_key="sk-ant-key")
        mock_resp = _mock_httpx_response(200, _anthropic_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.complete(_simple_request())

            _, kwargs = mock_client.post.call_args
            headers = kwargs["headers"]
            assert headers["x-api-key"] == "sk-ant-key"
            assert headers["anthropic-version"] == "2023-06-01"
            assert headers["content-type"] == "application/json"

    async def test_parse_text_response(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        mock_resp = _mock_httpx_response(200, _anthropic_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Hello from Claude!"
        assert result.tool_calls == []
        assert result.stop_reason == "stop"  # end_turn -> stop
        assert result.usage.prompt_tokens == 12
        assert result.usage.completion_tokens == 6
        assert result.usage.total_tokens == 18

    async def test_parse_tool_use_response(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        mock_resp = _mock_httpx_response(200, _anthropic_tool_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_1"
        assert result.tool_calls[0].name == "compute_tax"
        assert result.tool_calls[0].arguments == {"income": 800000}
        assert result.stop_reason == "tool_use"

    async def test_stop_reason_mapping(self):
        provider = AnthropicProvider(api_key="sk-ant-test")

        assert provider._map_stop_reason("end_turn") == "stop"
        assert provider._map_stop_reason("tool_use") == "tool_use"
        assert provider._map_stop_reason("max_tokens") == "length"
        assert provider._map_stop_reason("stop_sequence") == "stop"
        assert provider._map_stop_reason("unknown_reason") == "unknown_reason"

    async def test_retry_on_529_overloaded(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        resp_529 = _mock_httpx_response(529)
        resp_529.raise_for_status = MagicMock()
        resp_ok = _mock_httpx_response(200, _anthropic_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls, \
             patch("kara_api.llm.providers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [resp_529, resp_ok]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Hello from Claude!"
        mock_sleep.assert_called_once_with(1)


class TestAnthropicStream:
    async def test_streaming_events(self):
        provider = AnthropicProvider(api_key="sk-ant-test")

        sse_lines = [
            "event: message_start\n",
            'data: {"type":"message_start","message":{"model":"claude-sonnet-4-20250514"}}\n',
            "event: content_block_start\n",
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n',
            "event: content_block_delta\n",
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}\n',
            "event: content_block_delta\n",
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":" there"}}\n',
            "event: content_block_stop\n",
            'data: {"type":"content_block_stop","index":0}\n',
            "event: message_delta\n",
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"input_tokens":10,"output_tokens":5}}\n',
            "event: message_stop\n",
            'data: {"type":"message_stop"}\n',
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp.aiter_lines = fake_aiter_lines

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=_make_stream_context(mock_resp))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(_simple_request()):
                chunks.append(chunk)

        # text_delta "Hello", text_delta " there", usage chunk, final
        text_chunks = [c for c in chunks if c.content is not None]
        assert len(text_chunks) == 2
        assert text_chunks[0].content == "Hello"
        assert text_chunks[1].content == " there"

        usage_chunks = [c for c in chunks if c.usage is not None]
        assert len(usage_chunks) == 1
        assert usage_chunks[0].usage.prompt_tokens == 10
        assert usage_chunks[0].usage.completion_tokens == 5

        assert chunks[-1].is_final is True

    async def test_streaming_tool_use(self):
        provider = AnthropicProvider(api_key="sk-ant-test")

        sse_lines = [
            "event: message_start\n",
            'data: {"type":"message_start","message":{}}\n',
            "event: content_block_start\n",
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_1","name":"compute_tax"}}\n',
            "event: content_block_delta\n",
            'data: {"type":"content_block_delta","delta":{"type":"input_json_delta","partial_json":"{\\"income\\""}}\n',
            "event: content_block_delta\n",
            'data: {"type":"content_block_delta","delta":{"type":"input_json_delta","partial_json":": 500000}"}}\n',
            "event: content_block_stop\n",
            'data: {"type":"content_block_stop","index":0}\n',
            "event: message_stop\n",
            'data: {"type":"message_stop"}\n',
        ]

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp.aiter_lines = fake_aiter_lines

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=_make_stream_context(mock_resp))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(_simple_request()):
                chunks.append(chunk)

        tool_chunks = [c for c in chunks if c.tool_calls]
        assert len(tool_chunks) == 1
        tc = tool_chunks[0].tool_calls[0]
        assert tc.id == "toolu_1"
        assert tc.name == "compute_tax"
        assert tc.arguments == {"income": 500000}


# ---------------------------------------------------------------------------
# Ollama Provider Tests
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    def test_delegates_to_openai_with_correct_url(self):
        provider = OllamaProvider(base_url="http://myhost:11434", model="llama3.1")
        assert provider._openai.base_url == "http://myhost:11434/v1"
        assert provider._openai.api_key == "ollama"
        assert provider._openai.model == "llama3.1"

    async def test_complete_delegates(self):
        provider = OllamaProvider()
        mock_resp = _mock_httpx_response(200, _openai_text_response())

        with patch("kara_api.llm.providers.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.complete(_simple_request())

        assert result.content == "Hello there!"


# ---------------------------------------------------------------------------
# Fake Provider Tests
# ---------------------------------------------------------------------------


class TestFakeLLMProvider:
    async def test_default_response(self):
        provider = FakeLLMProvider()
        result = await provider.complete(_simple_request())

        assert result.content == "This is a fake LLM response."
        assert result.model == "fake"
        assert result.stop_reason == "stop"

    async def test_canned_queue(self):
        canned = [
            LLMResponse(content="First", model="fake", stop_reason="stop"),
            LLMResponse(content="Second", model="fake", stop_reason="stop"),
        ]
        provider = FakeLLMProvider(responses=canned)

        r1 = await provider.complete(_simple_request())
        r2 = await provider.complete(_simple_request())
        r3 = await provider.complete(_simple_request())

        assert r1.content == "First"
        assert r2.content == "Second"
        assert r3.content == "This is a fake LLM response."  # falls back to default

    async def test_records_request(self):
        provider = FakeLLMProvider()
        request = _simple_request("Track me")
        await provider.complete(request)

        assert provider.last_request is request
        assert provider._call_count == 1

    async def test_streaming_yields_words(self):
        provider = FakeLLMProvider(default_content="hello beautiful world")
        chunks = []
        async for chunk in provider.stream(_simple_request()):
            chunks.append(chunk)

        # 3 word chunks + 1 final
        assert len(chunks) == 4
        assert chunks[0].content == "hello "
        assert chunks[1].content == "beautiful "
        assert chunks[2].content == "world "
        assert chunks[3].is_final is True
        assert chunks[3].usage is not None


# ---------------------------------------------------------------------------
# Factory Tests
# ---------------------------------------------------------------------------


class TestGetLLMProvider:
    def test_returns_openai_provider(self):
        settings = Settings(
            LLM_PROVIDER="openai",
            LLM_API_KEY="sk-test",
            LLM_MODEL="gpt-4o",
            LLM_BASE_URL="",
        )
        provider = get_llm_provider(settings)
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "sk-test"
        assert provider.model == "gpt-4o"
        assert provider.base_url == "https://api.openai.com/v1"

    def test_openai_custom_base_url(self):
        settings = Settings(
            LLM_PROVIDER="openai",
            LLM_API_KEY="sk-test",
            LLM_BASE_URL="https://custom.api.example.com/v1",
        )
        provider = get_llm_provider(settings)
        assert isinstance(provider, OpenAIProvider)
        assert provider.base_url == "https://custom.api.example.com/v1"

    def test_returns_anthropic_provider(self):
        settings = Settings(
            LLM_PROVIDER="anthropic",
            LLM_API_KEY="sk-ant-test",
            LLM_MODEL="claude-sonnet-4-20250514",
        )
        provider = get_llm_provider(settings)
        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "sk-ant-test"

    def test_returns_ollama_provider(self):
        settings = Settings(
            LLM_PROVIDER="ollama",
            OLLAMA_BASE_URL="http://localhost:11434",
            LLM_MODEL="llama3.1",
        )
        provider = get_llm_provider(settings)
        assert isinstance(provider, OllamaProvider)

    def test_returns_fake_provider(self):
        settings = Settings(LLM_PROVIDER="fake")
        provider = get_llm_provider(settings)
        assert isinstance(provider, FakeLLMProvider)

    def test_raises_on_unknown_provider(self):
        settings = Settings(LLM_PROVIDER="unknown_provider")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider(settings)
