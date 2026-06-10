"""Tests for kara_api.routers.chat — chat endpoints with SSE streaming."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from kara_api.agent.loop import AgentResponse, ToolCallRecord
from kara_api.agent.session import SessionSummaryRow
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
        self.created_at = datetime(2026, 3, 29, 12, 0, 0, tzinfo=UTC)
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
        self.created_at = datetime(2026, 3, 29, 12, 0, 0, tzinfo=UTC)


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
    sm.list_sessions = AsyncMock(return_value=[])
    return sm


def _wire_run_stream(loop: AsyncMock) -> None:
    """Make loop.run_stream stream whatever loop.run would return.

    Delegating at call time means tests that override ``loop.run`` (with a
    custom response or a side_effect exception) automatically drive the
    streaming path too.
    """
    from kara_api.agent.loop import AgentStreamEvent

    def run_stream(*args, **kwargs):
        async def _gen():
            response = await loop.run(*args, **kwargs)
            for record in response.tool_calls_made:
                yield AgentStreamEvent(type="tool_result", record=record)
            if response.content:
                # Stream in two deltas to exercise accumulation
                half = max(1, len(response.content) // 2)
                yield AgentStreamEvent(type="content_delta", text=response.content[:half])
                yield AgentStreamEvent(type="content_delta", text=response.content[half:])
            yield AgentStreamEvent(type="done", response=response)

        return _gen()

    loop.run_stream = MagicMock(side_effect=run_stream)


@pytest.fixture
def mock_agent_loop():
    loop = AsyncMock()
    loop.run = AsyncMock(return_value=_make_agent_response())
    _wire_run_stream(loop)
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
    # Patch lifespan to skip DB init
    from contextlib import asynccontextmanager

    from kara_api.main import create_app

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

    async def test_create_chat_streams_content_deltas(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        deltas = [e for e in events if e["type"] == "content_delta"]
        assert len(deltas) >= 2  # token streaming, not a single blob
        assert "".join(e["text"] for e in deltas) == "Hello from Kara."

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
        # Internals are logged, never sent to the client
        assert "LLM exploded" not in error_events[0]["message"]
        assert "try again" in error_events[0]["message"].lower()

    async def test_done_event_has_session_id(self, client):
        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        done = [e for e in events if e["type"] == "done"]
        assert len(done) == 1
        assert done[0]["session_id"] == str(_SESSION_ID)


# ---------------------------------------------------------------------------
# TestListSessionsEndpoint
# ---------------------------------------------------------------------------


class TestRegimeComparisonSSE:
    """Tests for the regime_comparison SSE event emitted from compare_regimes results."""

    @staticmethod
    def _make_comparison_json(savings: int = 40_000, breakeven: int = 375_000) -> str:
        from kara_tax_engine.models import (
            AgeCategory,
            Regime,
            RegimeComparison,
            TaxBreakdown,
        )

        old = TaxBreakdown(
            regime=Regime.OLD,
            financial_year="2025-26",
            assessment_year="2026-27",
            age_category=AgeCategory.BELOW_60,
            total_tax_payable=180_000,
        )
        new = TaxBreakdown(
            regime=Regime.NEW,
            financial_year="2025-26",
            assessment_year="2026-27",
            age_category=AgeCategory.BELOW_60,
            total_tax_payable=140_000,
        )
        comparison = RegimeComparison(
            old_regime=old,
            new_regime=new,
            recommended_regime=Regime.NEW,
            savings=savings,
            breakeven_deductions=breakeven,
            explanation="New regime wins",
        )
        return comparison.model_dump_json()

    async def test_compare_regimes_emits_regime_comparison_event(
        self, client, mock_agent_loop
    ):
        comparison_json = self._make_comparison_json(savings=40_000)
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Here is the comparison.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compare_regimes",
                        arguments={"gross_salary": 1_500_000},
                        result=comparison_json,
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compare regimes"}
        )
        events = parse_sse_events(resp.text)
        comparison_events = [e for e in events if e["type"] == "regime_comparison"]
        assert len(comparison_events) == 1
        assert comparison_events[0]["comparison"]["savings"] == 40_000
        assert comparison_events[0]["comparison"]["recommended_regime"] == "new"

    async def test_compare_regimes_error_no_event(self, client, mock_agent_loop):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Comparison failed.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compare_regimes",
                        arguments={"gross_salary": 1_500_000},
                        result="Tool execution failed",
                        is_error=True,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compare regimes"}
        )
        events = parse_sse_events(resp.text)
        comparison_events = [e for e in events if e["type"] == "regime_comparison"]
        assert comparison_events == []

    async def test_compare_regimes_malformed_json_no_crash(
        self, client, mock_agent_loop
    ):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Comparison done.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compare_regimes",
                        arguments={"gross_salary": 1_500_000},
                        result="{invalid json",
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compare regimes"}
        )
        events = parse_sse_events(resp.text)
        # Stream must complete normally
        assert events[-1]["type"] == "done"
        # No regime_comparison event was emitted
        comparison_events = [e for e in events if e["type"] == "regime_comparison"]
        assert comparison_events == []
        # But the raw tool_result event is still present
        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "compare_regimes"


# ---------------------------------------------------------------------------
# TestDeductionGapsSSE
# ---------------------------------------------------------------------------


class TestDeductionGapsSSE:
    """Tests for the deduction_gaps SSE event emitted from find_deduction_gaps results."""

    @staticmethod
    def _make_optimization_json() -> str:
        from kara_tax_engine.models import OptimizationResult, OptimizationSuggestion

        return OptimizationResult(
            current_tax=200_000,
            optimized_tax=150_000,
            total_potential_saving=50_000,
            suggestions=[
                OptimizationSuggestion(
                    section="80C",
                    instrument="ELSS Mutual Fund",
                    suggested_amount=50_000,
                    potential_tax_saving=15_000,
                    lock_in_years=3,
                    expected_return_range=[10.0, 15.0],
                    note="",
                )
            ],
            section_80c_used=100_000,
            section_80c_remaining=50_000,
            section_80d_used=25_000,
            section_80d_remaining=0,
            section_80ccd_1b_used=0,
            section_80ccd_1b_remaining=50_000,
        ).model_dump_json()

    async def test_find_deduction_gaps_emits_deduction_gaps_event(
        self, client, mock_agent_loop
    ):
        optimization_json = self._make_optimization_json()
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Here are your tax saving opportunities.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="find_deduction_gaps",
                        arguments={},
                        result=optimization_json,
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Find deduction gaps"}
        )
        events = parse_sse_events(resp.text)
        deduction_events = [e for e in events if e["type"] == "deduction_gaps"]
        assert len(deduction_events) == 1
        assert deduction_events[0]["optimization"]["total_potential_saving"] == 50_000

    async def test_find_deduction_gaps_error_no_event(self, client, mock_agent_loop):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Could not find deduction gaps.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="find_deduction_gaps",
                        arguments={},
                        result="Tool execution failed",
                        is_error=True,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Find deduction gaps"}
        )
        events = parse_sse_events(resp.text)
        deduction_events = [e for e in events if e["type"] == "deduction_gaps"]
        assert deduction_events == []

    async def test_find_deduction_gaps_malformed_json_no_crash(
        self, client, mock_agent_loop
    ):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Done.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="find_deduction_gaps",
                        arguments={},
                        result="{invalid json",
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Find deduction gaps"}
        )
        events = parse_sse_events(resp.text)
        # Stream must complete normally
        assert events[-1]["type"] == "done"
        # No deduction_gaps event was emitted
        deduction_events = [e for e in events if e["type"] == "deduction_gaps"]
        assert deduction_events == []


# ---------------------------------------------------------------------------
# TestCapitalGainsSSE
# ---------------------------------------------------------------------------


class TestCapitalGainsSSE:
    """Tests for the capital_gains SSE event emitted from compute_capital_gains results."""

    @staticmethod
    def _make_gains_json(gains_list: list | None = None) -> str:
        import json

        from kara_tax_engine.models import AssetClass, CapitalGainsResult, GainType

        if gains_list is None:
            gains_list = [
                CapitalGainsResult(
                    asset_class=AssetClass.LISTED_EQUITY,
                    gain_type=GainType.LTCG,
                    section="112A",
                    purchase_price=500_000,
                    sale_price=750_000,
                    total_gain=250_000,
                    exempt_amount=125_000,
                    taxable_gain=125_000,
                    tax_rate=0.10,
                    tax_amount=12_500,
                    holding_months=18,
                    note="",
                )
            ]
        return json.dumps([g.model_dump(mode="json") for g in gains_list])

    async def test_compute_capital_gains_emits_capital_gains_event(
        self, client, mock_agent_loop
    ):
        gains_json = self._make_gains_json()
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Here is your capital gains summary.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compute_capital_gains",
                        arguments={},
                        result=gains_json,
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compute capital gains"}
        )
        events = parse_sse_events(resp.text)
        gains_events = [e for e in events if e["type"] == "capital_gains"]
        assert len(gains_events) == 1
        assert len(gains_events[0]["gains"]) == 1

    async def test_compute_capital_gains_empty_list(self, client, mock_agent_loop):
        import json

        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="No capital gains found.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compute_capital_gains",
                        arguments={},
                        result=json.dumps([]),
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compute capital gains"}
        )
        events = parse_sse_events(resp.text)
        gains_events = [e for e in events if e["type"] == "capital_gains"]
        assert len(gains_events) == 1
        assert gains_events[0]["gains"] == []

    async def test_compute_capital_gains_error_no_event(self, client, mock_agent_loop):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Capital gains computation failed.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compute_capital_gains",
                        arguments={},
                        result="Tool execution failed",
                        is_error=True,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compute capital gains"}
        )
        events = parse_sse_events(resp.text)
        gains_events = [e for e in events if e["type"] == "capital_gains"]
        assert gains_events == []

    async def test_compute_capital_gains_malformed_json_no_crash(
        self, client, mock_agent_loop
    ):
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(
                content="Done.",
                tool_calls=[
                    ToolCallRecord(
                        tool_name="compute_capital_gains",
                        arguments={},
                        result="{invalid json",
                        is_error=False,
                    )
                ],
            )
        )
        resp = await client.post(
            "/api/v1/chat", json={"message": "Compute capital gains"}
        )
        events = parse_sse_events(resp.text)
        # Stream must complete normally
        assert events[-1]["type"] == "done"
        # No capital_gains event was emitted
        gains_events = [e for e in events if e["type"] == "capital_gains"]
        assert gains_events == []


class TestListSessionsEndpoint:
    async def test_list_sessions_empty(self, client, mock_session_manager):
        mock_session_manager.list_sessions = AsyncMock(return_value=[])
        resp = await client.get("/api/v1/chat/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_sessions_returns_summary_rows(
        self, client, mock_session_manager
    ):
        sid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        sid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        ts_newer = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
        ts_older = datetime(2026, 4, 7, 9, 0, 0, tzinfo=UTC)
        mock_session_manager.list_sessions = AsyncMock(
            return_value=[
                SessionSummaryRow(
                    id=str(sid1),
                    created_at=ts_newer,
                    updated_at=ts_newer,
                    title="How much tax on 15 LPA?",
                    message_count=4,
                ),
                SessionSummaryRow(
                    id=str(sid2),
                    created_at=ts_older,
                    updated_at=ts_older,
                    title="New Chat",
                    message_count=0,
                ),
            ]
        )
        resp = await client.get("/api/v1/chat/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert set(body[0].keys()) == {
            "id",
            "created_at",
            "updated_at",
            "title",
            "message_count",
        }
        assert body[0]["id"] == str(sid1)
        assert body[0]["title"] == "How much tax on 15 LPA?"
        assert body[0]["message_count"] == 4
        assert body[1]["title"] == "New Chat"

    async def test_list_sessions_path_does_not_collide_with_session_uuid(
        self, client, mock_session_manager
    ):
        """Ensure ``GET /chat/sessions`` is matched as the list route, not as
        ``GET /chat/{session_id}`` with ``session_id="sessions"``."""
        mock_session_manager.list_sessions = AsyncMock(return_value=[])
        resp = await client.get("/api/v1/chat/sessions")
        # If the wrong route handled this, FastAPI would return 422 for an
        # invalid UUID path param.
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Agent loop wiring
# ---------------------------------------------------------------------------


class TestAgentLoopWiring:
    """The chat agent's ToolRegistry must have knowledge search wired in."""

    def _make_loop(self):
        from kara_api.config import Settings
        from kara_api.routers.chat import _create_agent_loop

        settings = Settings(LLM_PROVIDER="fake", _env_file=None)
        return _create_agent_loop(settings)

    def test_search_dependencies_are_wired(self):
        from kara_api.knowledge.search import hybrid_search

        loop = self._make_loop()
        registry = loop._registry
        assert registry._search_fn is hybrid_search
        assert registry._embedding_provider is not None
        assert registry._db_session_factory is not None

    @pytest.mark.asyncio
    async def test_search_tool_is_not_unconfigured(self):
        """search_tax_law must never report 'not configured' from the chat path.

        (Without an initialized DB it may fail with a runtime error, but the
        wiring itself must be present.)
        """
        from kara_api.llm.models import ToolCall

        loop = self._make_loop()
        tc = ToolCall(id="t1", name="search_tax_law", arguments={"query": "80C"})
        result = await loop._registry.execute(tc)
        assert "not configured" not in result.content


# ---------------------------------------------------------------------------
# Streaming robustness
# ---------------------------------------------------------------------------


class TestStreamingRobustness:
    async def test_user_message_persisted_even_when_agent_fails(
        self, client, mock_session_manager, mock_agent_loop
    ):
        """The user's message must be saved BEFORE the agent runs, so a
        provider failure can never silently swallow it."""

        def exploding_stream(*args, **kwargs):
            async def _gen():
                raise RuntimeError("provider exploded")
                yield  # pragma: no cover

            return _gen()

        mock_agent_loop.run_stream = MagicMock(side_effect=exploding_stream)

        resp = await client.post("/api/v1/chat", json={"message": "remember me"})
        events = parse_sse_events(resp.text)
        assert events[-1]["type"] == "error"

        persisted_roles = [c.args[1] for c in mock_session_manager.add_message.call_args_list]
        assert "user" in persisted_roles
        user_call = next(
            c for c in mock_session_manager.add_message.call_args_list if c.args[1] == "user"
        )
        assert user_call.args[2] == "remember me"

    async def test_sse_error_event_does_not_leak_internals(
        self, client, mock_agent_loop
    ):
        def exploding_stream(*args, **kwargs):
            async def _gen():
                raise RuntimeError("postgres password is hunter2")
                yield  # pragma: no cover

            return _gen()

        mock_agent_loop.run_stream = MagicMock(side_effect=exploding_stream)

        resp = await client.post("/api/v1/chat", json={"message": "Hi"})
        events = parse_sse_events(resp.text)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "hunter2" not in error_events[0]["message"]
        assert "RuntimeError" not in error_events[0]["message"]


# ---------------------------------------------------------------------------
# Card restoration on session reload
# ---------------------------------------------------------------------------


class TestSessionCards:
    """GET /chat/{id} must include structured card payloads derived from
    persisted tool results so the UI can rebuild cards after a reload."""

    @staticmethod
    def _breakdown_json() -> str:
        from kara_tax_engine import TaxComputer

        return TaxComputer("2025-26").compute(gross_salary=1_500_000).model_dump_json()

    async def test_get_session_rebuilds_tax_breakdown_card(
        self, client, mock_session_manager
    ):
        mock_session_manager.get_messages = AsyncMock(
            return_value=[
                _FakeDbMessage(role="user", content="tax on 15L?"),
                _FakeDbMessage(
                    role="assistant",
                    content="Here you go.",
                    tool_calls_json=[
                        {
                            "name": "compute_tax",
                            "args": {"gross_salary": 1_500_000},
                            "result": self._breakdown_json(),
                            "is_error": False,
                        }
                    ],
                ),
            ]
        )

        resp = await client.get(f"/api/v1/chat/{_SESSION_ID}")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assistant = messages[1]
        assert assistant["cards"] is not None
        assert assistant["cards"]["tax_breakdown"]["total_tax_payable"] == 97_500

    async def test_get_session_no_cards_for_plain_messages(
        self, client, mock_session_manager
    ):
        mock_session_manager.get_messages = AsyncMock(
            return_value=[_FakeDbMessage(role="assistant", content="Hi there")]
        )
        resp = await client.get(f"/api/v1/chat/{_SESSION_ID}")
        assert resp.json()["messages"][0]["cards"] is None

    async def test_persisted_tool_calls_include_results(
        self, client, mock_session_manager, mock_agent_loop
    ):
        """The SSE path must store tool results so cards survive a reload."""
        record = ToolCallRecord(
            tool_name="compute_tax",
            arguments={"gross_salary": 1},
            result='{"x": 1}',
            is_error=False,
        )
        mock_agent_loop.run = AsyncMock(
            return_value=_make_agent_response(tool_calls=[record])
        )

        await client.post("/api/v1/chat", json={"message": "Hi"})

        assistant_calls = [
            c
            for c in mock_session_manager.add_message.call_args_list
            if c.args[1] == "assistant"
        ]
        assert len(assistant_calls) == 1
        stored = assistant_calls[0].args[3]
        assert stored[0]["name"] == "compute_tax"
        assert stored[0]["result"] == '{"x": 1}'
        assert stored[0]["is_error"] is False
