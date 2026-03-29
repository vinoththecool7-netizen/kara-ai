"""Tests for kara_api.routers.chat — chat endpoints with SSE streaming."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from kara_api.agent.loop import AgentResponse, ToolCallRecord
from kara_api.llm.models import TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_sse_events(response_text: str) -> list[dict]:
    """Extract all ``data:`` lines from SSE response text."""
    events = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _make_agent_response(
    content: str = "Hello from Kara.",
    tool_calls: list[ToolCallRecord] | None = None,
    profile_snapshot: dict | None = None,
) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=tool_calls or [],
        total_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        iterations=1,
        profile_snapshot=profile_snapshot or {"slots": {}},
    )


# ---------------------------------------------------------------------------
# Fake DB session object
# ---------------------------------------------------------------------------


class _FakeDbSession:
    """Mimics DbSession for testing."""

    def __init__(self, session_id: uuid.UUID | None = None, profile_json: dict | None = None):
        self.id = session_id or uuid.uuid4()
        self.created_at = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        self.updated_at = self.created_at
        self.profile_json = profile_json or {}


class _FakeDbMessage:
    """Mimics DbMessage for testing."""

    def __init__(
        self,
        role: str = "user",
        content: str | None = "Hello",
        tool_calls_json: list[dict] | None = None,
    ):
        self.id = 1
        self.session_id = uuid.uuid4()
        self.role = role
        self.content = content
        self.tool_calls_json = tool_calls_json
        self.created_at = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SESSION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_session_manager():
    sm = AsyncMock()
    sm.create_session = AsyncMock(return_value=_SESSION_ID)
    sm.get_session = AsyncMock(return_value=_FakeDbSession(session_id=_SESSION_ID))
    sm.get_messages = AsyncMock(return_value=[])
    sm.add_message = AsyncMock(return_value=_FakeDbMessage())
    sm.update_profile = AsyncMock(return_value=True)
    sm.delete_session = AsyncMock(return_value=True)
    return sm


@pytest.fixture
def mock_agent_loop():
    loop = AsyncMock()
    loop.run = AsyncMock(return_value=_make_agent_response())
    return loop


@pytest.fixture
def patches(mock_session_manager, mock_agent_loop):
    """Patch _create_session_manager and _create_agent_loop in the chat module."""
    with (
        patch(
            "kara_api.routers.chat._create_session_manager",
            return_value=mock_session_manager,
        ),
        patch(
            "kara_api.routers.chat._create_agent_loop",
            return_value=mock_agent_loop,
        ),
    ):
        yield


@pytest.fixture
async def client(patches):
    """HTTP client with mocked dependencies — no DB/LLM required."""
    from kara_api.main import create_app

    # Patch lifespan to skip DB init
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    with patch("kara_api.main.lifespan", _noop_lifespan):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# TestCreateChat
# ---------------------------------------------------------------------------


class TestCreateChat:
    async def test_create_chat_returns_sse_stream(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    async def test_create_chat_stream_starts_with_session_created(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[0]["type"] == "session_created"

    async def test_create_chat_stream_has_content_event(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        content_events = [e for e in events if e["type"] == "content"]
        assert len(content_events) == 1
        assert content_events[0]["text"] == "Hello from Kara."

    async def test_create_chat_stream_ends_with_done(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        assert events[-1]["type"] == "done"

    async def test_create_chat_done_has_profile_state(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        done = events[-1]
        assert "profile_state" in done
        assert "slots" in done["profile_state"]
        assert "ready_intents" in done["profile_state"]

    async def test_create_chat_empty_message_422(self, client):
        resp = await client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestCreateChatJson
# ---------------------------------------------------------------------------


class TestCreateChatJson:
    async def test_json_accept_returns_json(self, client):
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Hi"},
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    async def test_json_response_has_all_fields(self, client):
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Hi"},
            headers={"Accept": "application/json"},
        )
        data = resp.json()
        assert "session_id" in data
        assert "response" in data
        assert "tool_calls_made" in data
        assert "profile_state" in data
        assert data["response"] == "Hello from Kara."


# ---------------------------------------------------------------------------
# TestContinueChat
# ---------------------------------------------------------------------------


class TestContinueChat:
    async def test_continue_returns_sse_stream(self, client):
        resp = await client.post(
            f"/api/v1/chat/{_SESSION_ID}",
            json={"message": "What is 80C?"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = parse_sse_events(resp.text)
        assert events[0]["type"] == "session_created"

    async def test_continue_nonexistent_404(
        self, client, mock_session_manager
    ):
        mock_session_manager.get_session = AsyncMock(return_value=None)
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/chat/{fake_id}",
            json={"message": "Hello"},
        )
        assert resp.status_code == 404

    async def test_continue_preserves_history(
        self, client, mock_session_manager, mock_agent_loop
    ):
        mock_session_manager.get_messages = AsyncMock(
            return_value=[
                _FakeDbMessage(role="user", content="First message"),
                _FakeDbMessage(role="assistant", content="First reply"),
            ]
        )
        resp = await client.post(
            f"/api/v1/chat/{_SESSION_ID}",
            json={"message": "Second message"},
        )
        assert resp.status_code == 200

        # Verify agent_loop.run was called with non-empty history
        call_args = mock_agent_loop.run.call_args
        history_arg = call_args.kwargs.get("history", call_args.args[1] if len(call_args.args) > 1 else [])
        assert len(history_arg) == 2


# ---------------------------------------------------------------------------
# TestGetSession
# ---------------------------------------------------------------------------


class TestGetSession:
    async def test_get_session_returns_history(self, client, mock_session_manager):
        mock_session_manager.get_messages = AsyncMock(
            return_value=[
                _FakeDbMessage(role="user", content="Hello"),
                _FakeDbMessage(role="assistant", content="Hi there!"),
            ]
        )
        resp = await client.get(f"/api/v1/chat/{_SESSION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(_SESSION_ID)
        assert "profile_state" in data
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"

    async def test_get_nonexistent_404(self, client, mock_session_manager):
        mock_session_manager.get_session = AsyncMock(return_value=None)
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/chat/{fake_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestDeleteSession
# ---------------------------------------------------------------------------


class TestDeleteSession:
    async def test_delete_returns_success(self, client):
        resp = await client.delete(f"/api/v1/chat/{_SESSION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"

    async def test_delete_nonexistent_404(self, client, mock_session_manager):
        mock_session_manager.delete_session = AsyncMock(return_value=False)
        fake_id = uuid.uuid4()
        resp = await client.delete(f"/api/v1/chat/{fake_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestSSEFormat
# ---------------------------------------------------------------------------


class TestSSEFormat:
    async def test_sse_events_are_valid_json(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Test"})
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                parsed = json.loads(line[6:])
                assert isinstance(parsed, dict)
                assert "type" in parsed

    async def test_tool_result_events_for_tool_calls(
        self, client, mock_agent_loop
    ):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Tax computed.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compute_tax",
                        arguments={"gross_salary": 1500000},
                        result='{"total_tax": 112500}',
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post("/api/v1/chat", json={"message": "Compute my tax"})
        events = parse_sse_events(resp.text)
        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "compute_tax"
        assert tool_events[0]["is_error"] is False

    async def test_advisory_events_present(
        self, client, mock_agent_loop
    ):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Tax computed.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compute_tax",
                        arguments={"gross_salary": 1500000},
                        result='{"total_tax": 112500}',
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post("/api/v1/chat", json={"message": "Compute my tax"})
        events = parse_sse_events(resp.text)
        advisory_events = [e for e in events if e["type"] == "advisory"]
        # compute_tax without compare_regimes triggers an advisory
        assert len(advisory_events) >= 1
        assert "hint" in advisory_events[0]

    async def test_error_event_on_failure(
        self, client, mock_agent_loop
    ):
        mock_agent_loop.run = AsyncMock(side_effect=RuntimeError("LLM exploded"))
        resp = await client.post("/api/v1/chat", json={"message": "Break"})
        events = parse_sse_events(resp.text)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "LLM exploded" in error_events[0]["message"]

    async def test_done_event_has_session_id(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        done = [e for e in events if e["type"] == "done"]
        assert len(done) == 1
        assert done[0]["session_id"] == str(_SESSION_ID)
