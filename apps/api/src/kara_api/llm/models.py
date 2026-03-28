"""Unified LLM data models for Kara.

Normalises OpenAI / Anthropic / Ollama response format differences into a
single internal representation so the rest of the codebase never has to care
which provider is in use.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Chat message roles."""

    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ToolCall(BaseModel):
    """A single tool/function invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    """A chat message in the conversation history."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None


class ToolDefinition(BaseModel):
    """Description of a tool the model is allowed to call.

    ``parameters`` must be a valid JSON Schema object describing the tool's
    accepted arguments.
    """

    name: str
    description: str
    parameters: dict[str, Any]


class LLMRequest(BaseModel):
    """Provider-agnostic request payload sent to an LLM."""

    messages: list[Message]
    tools: list[ToolDefinition] = Field(default_factory=list)
    temperature: float = 0.3
    max_tokens: int = 4096
    stream: bool = False


class TokenUsage(BaseModel):
    """Token consumption reported by the provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Provider-agnostic response returned from an LLM."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""
    stop_reason: str = ""


class StreamChunk(BaseModel):
    """A single chunk emitted during streaming responses."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    is_final: bool = False
    usage: TokenUsage | None = None
