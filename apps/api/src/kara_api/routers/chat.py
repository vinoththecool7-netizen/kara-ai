"""Chat endpoints: SSE streaming conversation API.

Wires together AgentLoop, SessionManager, AdvisoryTriggers, and
ProfileBuilder into HTTP endpoints with Server-Sent Events streaming.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from kara_tax_engine.models import (
    CapitalGainsResult,
    OptimizationResult,
    RegimeComparison,
    TaxBreakdown,
)

from kara_api.agent import (
    ENHANCED_SYSTEM_PROMPT,
    AdvisoryTriggers,
    AgentLoop,
    AgentResponse,
    ProfileBuilder,
    SessionManager,
)
from kara_api.config import Settings, get_settings
from kara_api.db.connection import get_session_factory
from kara_api.db.models import Message as DbMessage
from kara_api.knowledge.embeddings import get_embedding_provider
from kara_api.knowledge.search import hybrid_search
from kara_api.llm.client import LLMClient
from kara_api.llm.models import Message, Role, ToolCall
from kara_api.llm.providers import get_llm_provider
from kara_api.tools.executor import ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    role: str
    content: str | None
    tool_calls: list[dict] | None = None
    created_at: str


class ProfileState(BaseModel):
    slots: dict[str, Any]
    ready_intents: list[str]


class SessionResponse(BaseModel):
    session_id: str  # UUID as string
    created_at: str
    profile_state: ProfileState
    messages: list[MessageResponse]


class SessionSummary(BaseModel):
    """Lightweight projection of a chat session for sidebar listing."""

    id: str
    created_at: str
    updated_at: str
    title: str
    message_count: int


class ChatResponse(BaseModel):
    """Non-streaming fallback response."""

    session_id: str
    response: str
    tool_calls_made: list[dict]
    profile_state: ProfileState


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _lazy_db_session():
    """Open an AsyncSession, resolving the factory at call time.

    The engine/session factory only exists after app startup (init_db), so
    the ToolRegistry gets this thin indirection instead of the factory itself.
    """
    return get_session_factory()()


def _create_agent_loop(settings: Settings) -> AgentLoop:
    provider = get_llm_provider(settings)
    client = LLMClient(provider, system_prompt=ENHANCED_SYSTEM_PROMPT)
    registry = ToolRegistry(
        search_fn=hybrid_search,
        db_session_factory=_lazy_db_session,
        embedding_provider=get_embedding_provider(settings),
    )
    return AgentLoop(llm_client=client, tool_registry=registry)


def _create_session_manager() -> SessionManager:
    return SessionManager(get_session_factory())


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _db_messages_to_llm(db_msgs: list[DbMessage]) -> list[Message]:
    """Convert DB message rows to LLM Message objects."""
    return [
        Message(
            role=Role(m.role),
            content=m.content,
            tool_calls=(
                [
                    ToolCall(
                        id=tc.get("id", f"call_{i}"),
                        name=tc["name"],
                        arguments=tc.get("args", tc.get("arguments", {})),
                    )
                    for i, tc in enumerate(m.tool_calls_json)
                ]
                if m.tool_calls_json
                else []
            ),
        )
        for m in db_msgs
    ]


def _build_profile_state(profile: ProfileBuilder) -> ProfileState:
    return ProfileState(
        slots=profile.get_filled_slots(),
        ready_intents=[i.value for i in profile.get_ready_intents()],
    )


def _db_messages_to_response(db_msgs: list[DbMessage]) -> list[MessageResponse]:
    """Convert DB message rows to API response models."""
    return [
        MessageResponse(
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls_json,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in db_msgs
    ]


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


# SSE event types emitted by _sse_generator (and by /documents/upload via client):
#   "session_created"  — session UUID on new chat
#   "tool_result"      — raw tool call result
#   "tax_breakdown"    — structured TaxBreakdown from compute_tax tool
#   "regime_comparison"— structured RegimeComparison from compare_regimes tool
#   "deduction_gaps"   — structured OptimizationResult from find_deduction_gaps tool
#   "capital_gains"    — structured CapitalGainsResult list from compute_capital_gains tool
#   "document_parsed"  — emitted after a document upload auto-fills the profile
#   "content"          — assistant text content
#   "advisory"         — advisory hint
#   "done"             — final event with profile state
#   "error"            — error event
async def _sse_generator(
    agent_loop: AgentLoop,
    session_manager: SessionManager,
    advisory: AdvisoryTriggers,
    session_id: uuid.UUID,
    user_message: str,
    history: list[Message],
    profile: ProfileBuilder,
) -> AsyncIterator[str]:
    try:
        yield f"data: {json.dumps({'type': 'session_created', 'session_id': str(session_id)})}\n\n"

        result: AgentResponse = await agent_loop.run(
            user_message, history=history, profile=profile
        )

        # Emit tool results
        for record in result.tool_calls_made:
            yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': record.tool_name, 'result': record.result, 'is_error': record.is_error})}\n\n"

            # Emit structured tax_breakdown event for compute_tax tool
            if record.tool_name == "compute_tax" and not record.is_error:
                try:
                    breakdown = TaxBreakdown.model_validate(json.loads(record.result))
                    yield f"data: {json.dumps({'type': 'tax_breakdown', 'breakdown': breakdown.model_dump(mode='json')})}\n\n"
                except (json.JSONDecodeError, ValidationError) as exc:
                    logger.warning("Failed to parse tax_breakdown from compute_tax result: %s", exc)

            if record.tool_name == "compare_regimes" and not record.is_error:
                try:
                    comparison = RegimeComparison.model_validate(json.loads(record.result))
                    yield f"data: {json.dumps({'type': 'regime_comparison', 'comparison': comparison.model_dump(mode='json')})}\n\n"
                except (json.JSONDecodeError, ValidationError) as exc:
                    logger.warning("Failed to parse regime_comparison from compare_regimes result: %s", exc)

            if record.tool_name == "find_deduction_gaps" and not record.is_error:
                try:
                    optimization = OptimizationResult.model_validate(json.loads(record.result))
                    yield f"data: {json.dumps({'type': 'deduction_gaps', 'optimization': optimization.model_dump(mode='json')})}\n\n"
                except (json.JSONDecodeError, ValidationError) as exc:
                    logger.warning("Failed to parse deduction_gaps from find_deduction_gaps result: %s", exc)

            if record.tool_name == "compute_capital_gains" and not record.is_error:
                try:
                    raw_list = json.loads(record.result)
                    gains = [CapitalGainsResult.model_validate(item) for item in raw_list]
                    yield f"data: {json.dumps({'type': 'capital_gains', 'gains': [g.model_dump(mode='json') for g in gains]})}\n\n"
                except (json.JSONDecodeError, ValidationError) as exc:
                    logger.warning("Failed to parse capital_gains from compute_capital_gains result: %s", exc)

        # Emit content
        if result.content:
            yield f"data: {json.dumps({'type': 'content', 'text': result.content})}\n\n"

        # Advisory hints
        tool_names = [r.tool_name for r in result.tool_calls_made]
        for hint in advisory.check(tool_names):
            yield f"data: {json.dumps({'type': 'advisory', 'hint': hint})}\n\n"

        # Persist user message
        await session_manager.add_message(session_id, "user", user_message)

        # Persist assistant message
        await session_manager.add_message(
            session_id,
            "assistant",
            result.content,
            (
                [{"name": r.tool_name, "args": r.arguments} for r in result.tool_calls_made]
                or None
            ),
        )

        # Update profile
        await session_manager.update_profile(session_id, result.profile_snapshot)

        # Done event
        profile_state = _build_profile_state(profile)
        yield f"data: {json.dumps({'type': 'done', 'session_id': str(session_id), 'profile_state': profile_state.model_dump()})}\n\n"

    except Exception as exc:
        logger.exception("SSE stream error")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"


# ---------------------------------------------------------------------------
# Non-streaming fallback
# ---------------------------------------------------------------------------


async def _run_json_response(
    agent_loop: AgentLoop,
    session_manager: SessionManager,
    advisory: AdvisoryTriggers,
    session_id: uuid.UUID,
    user_message: str,
    history: list[Message],
    profile: ProfileBuilder,
) -> ChatResponse:
    """Run the agent and return a plain JSON response."""
    result = await agent_loop.run(user_message, history=history, profile=profile)

    # Persist user message
    await session_manager.add_message(session_id, "user", user_message)

    # Persist assistant message
    await session_manager.add_message(
        session_id,
        "assistant",
        result.content,
        (
            [{"name": r.tool_name, "args": r.arguments} for r in result.tool_calls_made]
            or None
        ),
    )

    # Update profile
    await session_manager.update_profile(session_id, result.profile_snapshot)

    profile_state = _build_profile_state(profile)

    return ChatResponse(
        session_id=str(session_id),
        response=result.content,
        tool_calls_made=[
            {"tool_name": r.tool_name, "arguments": r.arguments, "result": r.result, "is_error": r.is_error}
            for r in result.tool_calls_made
        ],
        profile_state=profile_state,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def create_chat(body: ChatRequest, request: Request):
    """Create a new chat session and process the first message.

    Returns SSE stream by default, or JSON if ``Accept: application/json``.
    """
    settings = get_settings()
    agent_loop = _create_agent_loop(settings)
    sm = _create_session_manager()
    advisory = AdvisoryTriggers()

    session_id = await sm.create_session()
    profile = ProfileBuilder()
    history: list[Message] = []

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return await _run_json_response(
            agent_loop, sm, advisory, session_id, body.message, history, profile
        )

    return StreamingResponse(
        _sse_generator(agent_loop, sm, advisory, session_id, body.message, history, profile),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}")
async def continue_chat(session_id: uuid.UUID, body: ChatRequest, request: Request):
    """Continue an existing chat session with a new message.

    Returns SSE stream by default, or JSON if ``Accept: application/json``.
    """
    settings = get_settings()
    agent_loop = _create_agent_loop(settings)
    sm = _create_session_manager()
    advisory = AdvisoryTriggers()

    db_session = await sm.get_session(session_id)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Rebuild profile from persisted state
    profile_data = db_session.profile_json or {}
    profile = ProfileBuilder.from_dict(profile_data) if profile_data else ProfileBuilder()

    # Load message history
    db_msgs = await sm.get_messages(session_id)
    history = _db_messages_to_llm(db_msgs)

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return await _run_json_response(
            agent_loop, sm, advisory, session_id, body.message, history, profile
        )

    return StreamingResponse(
        _sse_generator(agent_loop, sm, advisory, session_id, body.message, history, profile),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions():
    """Return all chat sessions, newest first, with derived titles.

    Each row contains an ``id``, ``created_at``, ``updated_at``, a ``title``
    derived from the first user message (truncated to 60 chars + ellipsis,
    or ``"New Chat"`` when no user message exists), and ``message_count``.

    NOTE: This route must remain declared *before* ``/{session_id}`` so the
    literal path "/sessions" is not parsed as a UUID path parameter.
    """
    sm = _create_session_manager()
    rows = await sm.list_sessions()
    return [
        SessionSummary(
            id=row.id,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            title=row.title,
            message_count=row.message_count,
        )
        for row in rows
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID):
    """Fetch session history and profile state."""
    sm = _create_session_manager()

    db_session = await sm.get_session(session_id)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    db_msgs = await sm.get_messages(session_id)

    profile_data = db_session.profile_json or {}
    profile = ProfileBuilder.from_dict(profile_data) if profile_data else ProfileBuilder()
    profile_state = _build_profile_state(profile)

    return SessionResponse(
        session_id=str(session_id),
        created_at=db_session.created_at.isoformat() if db_session.created_at else "",
        profile_state=profile_state,
        messages=_db_messages_to_response(db_msgs),
    )


@router.delete("/{session_id}")
async def delete_session(session_id: uuid.UUID):
    """Delete a session and all its messages."""
    sm = _create_session_manager()

    deleted = await sm.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "deleted", "session_id": str(session_id)}
