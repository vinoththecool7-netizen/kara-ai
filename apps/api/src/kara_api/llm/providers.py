"""LLM provider abstraction layer.

Concrete providers for OpenAI, Anthropic, Ollama, and a fake/test provider.
All use raw httpx -- no external AI SDKs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from kara_api.config import Settings
from kara_api.llm.models import (
    LLMRequest,
    LLMResponse,
    Role,
    StreamChunk,
    TokenUsage,
    ToolCall,
)
from kara_api.tools.converters import (
    parse_anthropic_tool_calls,
    parse_openai_tool_calls,
    to_anthropic_tools,
    to_openai_tools,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMStreamError(Exception):
    """A provider aborted or stalled an HTTP-200 SSE stream.

    OpenAI-compatible backends (Groq, OpenRouter) and Anthropic can accept a
    request, return 200, and then deliver an error *inside* the stream (e.g.
    Groq's tool_use_failed schema validation, overloaded_error) — or hold the
    stream open with keep-alive comments while never producing data.
    """


def _error_message(err) -> str:
    if isinstance(err, dict):
        return err.get("message") or str(err)
    return str(err)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class LLMProvider(Protocol):
    """Protocol that all LLM providers must satisfy."""

    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]: ...


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIProvider:
    """OpenAI chat-completion provider using the REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        fallback_models: list[str] | None = None,
        *,
        stall_timeout: float = 90.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        # OpenRouter-only routing: alternates tried when the primary model's
        # pool is congested/rate-limited. Ignored for other base URLs.
        self.fallback_models = fallback_models or []
        # Max seconds a stream may go without a data frame. Keep-alive
        # comments reset the socket read timeout, so a congested pool can
        # otherwise hold a request open forever with zero output.
        self.stall_timeout = stall_timeout

    # -- helpers ----------------------------------------------------------

    def _build_payload(self, request: LLMRequest) -> dict:
        """Convert an LLMRequest into OpenAI-compatible JSON."""
        messages = []
        for msg in request.messages:
            entry: dict = {"role": msg.role.value, "content": msg.content or ""}
            if msg.role == Role.tool and msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(entry)

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if self.fallback_models and "openrouter" in self.base_url:
            payload["models"] = [self.model, *self.fallback_models]

        if request.tools:
            payload["tools"] = to_openai_tools(request.tools)

        return payload

    def _parse_response(self, data: dict) -> LLMResponse:
        """Parse an OpenAI chat-completion JSON response."""
        choice = data["choices"][0]
        message = choice["message"]

        content = message.get("content")
        tool_calls: list[ToolCall] = []
        if message.get("tool_calls"):
            tool_calls = parse_openai_tool_calls(message["tool_calls"])

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model", self.model),
            stop_reason=choice.get("finish_reason", ""),
        )

    # -- public API -------------------------------------------------------

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """POST to chat/completions with retry on 429/5xx."""
        payload = self._build_payload(request)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return self._parse_response(response.json())
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status == 429 or status >= 500:
                        last_exc = exc
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                    raise
            # After max retries
            raise last_exc  # type: ignore[misc]

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Stream chat completions via SSE."""
        payload = self._build_payload(request)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # read applies between received chunks AND to the wait for response
        # headers — 45s turns a silently stalled provider (congested free
        # pools hold requests without answering) into a visible error event
        # instead of a 2-minute frozen spinner.
        timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
        # Tool-call arguments arrive as string fragments spread across many
        # chunks, keyed by index; accumulate and flush as complete ToolCalls.
        tool_buf: dict[int, dict] = {}

        def _flush_tool_calls() -> list[ToolCall]:
            calls: list[ToolCall] = []
            for idx in sorted(tool_buf):
                buf = tool_buf[idx]
                try:
                    args = json.loads(buf["arguments"]) if buf["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                calls.append(
                    ToolCall(id=buf["id"] or f"call_{idx}", name=buf["name"], arguments=args)
                )
            tool_buf.clear()
            return calls

        last_data = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        # Keep-alive comments (e.g. ": OPENROUTER PROCESSING")
                        # arrive while a request sits in a congested queue and
                        # reset the read timeout; bound the wait ourselves.
                        if time.monotonic() - last_data > self.stall_timeout:
                            raise LLMStreamError(
                                f"Provider sent no data for {self.stall_timeout:.0f}s "
                                "(stream stalled — the model's pool may be congested; "
                                "retry or switch models)"
                            )
                        continue
                    last_data = time.monotonic()
                    data_str = line[len("data: "):]
                    if data_str == "[DONE]":
                        pending = _flush_tool_calls()
                        if pending:
                            yield StreamChunk(tool_calls=pending)
                        yield StreamChunk(is_final=True)
                        return
                    data = json.loads(data_str)
                    if data.get("error"):
                        # Groq/OpenRouter abort HTTP-200 streams with an error
                        # frame (e.g. Groq's tool_use_failed schema check);
                        # swallowing it would end the turn as a silent empty
                        # reply.
                        raise LLMStreamError(
                            f"Provider stream error: {_error_message(data['error'])}"
                        )
                    choice = data.get("choices", [{}])[0] if data.get("choices") else {}
                    delta = choice.get("delta", {})

                    for tc_delta in delta.get("tool_calls") or []:
                        idx = tc_delta.get("index", 0)
                        buf = tool_buf.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        if tc_delta.get("id"):
                            buf["id"] = tc_delta["id"]
                        fn = tc_delta.get("function") or {}
                        if fn.get("name"):
                            buf["name"] = fn["name"]
                        if fn.get("arguments"):
                            buf["arguments"] += fn["arguments"]

                    chunk = StreamChunk(content=delta.get("content"))

                    if choice.get("finish_reason"):
                        chunk.tool_calls = _flush_tool_calls()

                    # Check for usage in the chunk (sent with stream_options)
                    if data.get("usage"):
                        u = data["usage"]
                        chunk.usage = TokenUsage(
                            prompt_tokens=u.get("prompt_tokens", 0),
                            completion_tokens=u.get("completion_tokens", 0),
                            total_tokens=u.get("total_tokens", 0),
                        )

                    yield chunk


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicProvider:
    """Anthropic Messages API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_version = "2023-06-01"

    # -- helpers ----------------------------------------------------------

    def _build_payload(self, request: LLMRequest) -> dict:
        """Convert an LLMRequest into Anthropic Messages API format."""
        system_text: str | None = None
        messages = []
        for msg in request.messages:
            if msg.role == Role.system:
                system_text = msg.content or ""
                continue

            if msg.role == Role.tool and msg.tool_call_id:
                # Anthropic expects tool results as user messages with
                # content blocks of type "tool_result". Results for tools
                # called in the same assistant turn must share one user
                # message, so append to the previous tool-result turn.
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content or "",
                }
                if (
                    messages
                    and messages[-1]["role"] == "user"
                    and isinstance(messages[-1]["content"], list)
                ):
                    messages[-1]["content"].append(block)
                else:
                    messages.append({"role": "user", "content": [block]})
                continue

            entry: dict = {"role": msg.role.value, "content": msg.content or ""}
            if msg.role == Role.assistant and msg.tool_calls:
                # Each tool_result sent later must reference a tool_use block
                # emitted here — the API rejects the request otherwise.
                blocks: list[dict] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                    for tc in msg.tool_calls
                )
                entry["content"] = blocks
            messages.append(entry)

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if system_text is not None:
            payload["system"] = system_text

        if request.tools:
            payload["tools"] = to_anthropic_tools(request.tools)

        return payload

    @staticmethod
    def _map_stop_reason(reason: str) -> str:
        mapping = {
            "end_turn": "stop",
            "tool_use": "tool_use",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }
        return mapping.get(reason, reason)

    def _parse_response(self, data: dict) -> LLMResponse:
        """Parse an Anthropic Messages API response."""
        content_blocks = data.get("content", [])

        # Extract text content
        text_parts = [
            block["text"] for block in content_blocks if block.get("type") == "text"
        ]
        content = "\n".join(text_parts) if text_parts else None

        # Extract tool calls
        tool_calls = parse_anthropic_tool_calls(content_blocks)

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=(
                usage_data.get("input_tokens", 0)
                + usage_data.get("output_tokens", 0)
            ),
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model", self.model),
            stop_reason=self._map_stop_reason(data.get("stop_reason", "")),
        )

    # -- public API -------------------------------------------------------

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """POST to /v1/messages with retry on 429/529."""
        payload = self._build_payload(request)
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }

        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code in (429, 529) or response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return self._parse_response(response.json())
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status in (429, 529) or status >= 500:
                        last_exc = exc
                        if attempt < 2:
                            await asyncio.sleep(2**attempt)
                            continue
                    raise
            raise last_exc  # type: ignore[misc]

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Stream messages via Anthropic SSE events."""
        payload = self._build_payload(request)
        payload["stream"] = True

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }

        # read applies between received chunks AND to the wait for response
        # headers — 45s turns a silently stalled provider (congested free
        # pools hold requests without answering) into a visible error event
        # instead of a 2-minute frozen spinner.
        timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
        # Buffer for accumulating tool call JSON across delta events
        current_tool: dict | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                event_type: str = ""
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if line.startswith("event: "):
                        event_type = line[len("event: "):]
                        continue
                    if not line.startswith("data: "):
                        continue

                    data = json.loads(line[len("data: "):])

                    if event_type == "error":
                        # e.g. overloaded_error mid-stream on an HTTP-200
                        # response; must surface, not end as an empty reply.
                        raise LLMStreamError(
                            "Provider stream error: "
                            f"{_error_message(data.get('error', data))}"
                        )

                    if event_type == "content_block_start":
                        block = data.get("content_block", {})
                        if block.get("type") == "tool_use":
                            current_tool = {
                                "id": block["id"],
                                "name": block["name"],
                                "input_json": "",
                            }

                    elif event_type == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield StreamChunk(content=delta.get("text"))
                        elif delta.get("type") == "input_json_delta":
                            if current_tool is not None:
                                current_tool["input_json"] += delta.get(
                                    "partial_json", ""
                                )

                    elif event_type == "content_block_stop":
                        if current_tool is not None:
                            try:
                                args = json.loads(current_tool["input_json"])
                            except (json.JSONDecodeError, TypeError):
                                args = {}
                            yield StreamChunk(
                                tool_calls=[
                                    ToolCall(
                                        id=current_tool["id"],
                                        name=current_tool["name"],
                                        arguments=args,
                                    )
                                ]
                            )
                            current_tool = None

                    elif event_type == "message_delta":
                        # May contain usage
                        usage_data = data.get("usage", {})
                        if usage_data:
                            yield StreamChunk(
                                usage=TokenUsage(
                                    prompt_tokens=usage_data.get("input_tokens", 0),
                                    completion_tokens=usage_data.get(
                                        "output_tokens", 0
                                    ),
                                    total_tokens=(
                                        usage_data.get("input_tokens", 0)
                                        + usage_data.get("output_tokens", 0)
                                    ),
                                )
                            )

                    elif event_type == "message_stop":
                        yield StreamChunk(is_final=True)
                        return


# ---------------------------------------------------------------------------
# Ollama (delegates to OpenAI-compatible API)
# ---------------------------------------------------------------------------


class OllamaProvider:
    """Ollama provider -- delegates to OpenAI-compatible API at /v1."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
    ):
        self.model = model
        self._openai = OpenAIProvider(
            api_key="ollama",
            model=model,
            base_url=f"{base_url.rstrip('/')}/v1",
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return await self._openai.complete(request)

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        async for chunk in self._openai.stream(request):
            yield chunk


# ---------------------------------------------------------------------------
# Fake (for testing)
# ---------------------------------------------------------------------------


class FakeLLMProvider:
    """Deterministic fake provider for testing -- no network I/O."""

    def __init__(
        self,
        responses: list[LLMResponse] | None = None,
        default_content: str = "This is a fake LLM response.",
    ):
        self._responses: list[LLMResponse] = list(responses) if responses else []
        self._default_content = default_content
        self._call_count = 0
        self.last_request: LLMRequest | None = None

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        self._call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(
            content=self._default_content,
            model="fake",
            stop_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        response = await self.complete(request)
        words = (response.content or "").split()
        for word in words:
            yield StreamChunk(content=word + " ")
        if response.tool_calls:
            yield StreamChunk(tool_calls=response.tool_calls)
        yield StreamChunk(
            is_final=True,
            usage=response.usage,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Return the configured LLM provider based on settings."""
    provider_name = settings.LLM_PROVIDER.lower()

    if provider_name == "openai":
        base_url = settings.LLM_BASE_URL or "https://api.openai.com/v1"
        fallbacks = [
            m.strip() for m in settings.LLM_FALLBACK_MODELS.split(",") if m.strip()
        ]
        return OpenAIProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=base_url,
            fallback_models=fallbacks,
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )
    elif provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
        )
    elif provider_name == "fake":
        return FakeLLMProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
