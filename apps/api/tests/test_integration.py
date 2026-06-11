"""End-to-end integration tests for Kara API.

Tests the full pipeline: HTTP request → chat router → AgentLoop
→ real ToolRegistry (with FakeLLMProvider) → real tax engine → SSE/JSON response.

No database required — InMemorySessionManager replaces PostgreSQL-backed
SessionManager entirely.
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from kara_api.agent import ENHANCED_SYSTEM_PROMPT
from kara_api.agent.loop import AgentLoop
from kara_api.llm.client import LLMClient
from kara_api.llm.models import LLMResponse, Role, TokenUsage, ToolCall
from kara_api.llm.providers import FakeLLMProvider
from kara_api.tools.executor import ToolRegistry

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


def _tool_call(name: str, arguments: dict[str, Any], call_id: str | None = None) -> ToolCall:
    """Convenience constructor for a ToolCall."""
    return ToolCall(id=call_id or f"call_{name}", name=name, arguments=arguments)


def _fake_response(
    content: str | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> LLMResponse:
    """Build an LLMResponse with sane defaults."""
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        model="fake",
        stop_reason="stop" if not tool_calls else "tool_use",
    )


# ---------------------------------------------------------------------------
# InMemorySessionManager
# ---------------------------------------------------------------------------


@dataclass
class InMemorySession:
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    profile_json: dict[str, Any]


@dataclass
class InMemoryMessage:
    id: int
    session_id: uuid.UUID
    role: str
    content: str | None
    tool_calls_json: list[dict] | None
    created_at: datetime


class InMemorySessionManager:
    """SessionManager that stores data in plain Python dicts — no DB needed."""

    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, InMemorySession] = {}
        self._messages: dict[uuid.UUID, list[InMemoryMessage]] = {}
        self._next_msg_id: int = 1

    async def create_session(self, profile_data: dict[str, Any] | None = None) -> uuid.UUID:
        session_id = uuid.uuid4()
        now = datetime.now(tz=UTC)
        self._sessions[session_id] = InMemorySession(
            id=session_id,
            created_at=now,
            updated_at=now,
            profile_json=profile_data or {},
        )
        self._messages[session_id] = []
        return session_id

    async def get_session(self, session_id: uuid.UUID) -> InMemorySession | None:
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: uuid.UUID) -> bool:
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        self._messages.pop(session_id, None)
        return True

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str | None,
        tool_calls: list[dict] | None = None,
    ) -> InMemoryMessage:
        now = datetime.now(tz=UTC)
        msg = InMemoryMessage(
            id=self._next_msg_id,
            session_id=session_id,
            role=role,
            content=content,
            tool_calls_json=tool_calls,
            created_at=now,
        )
        self._next_msg_id += 1
        if session_id not in self._messages:
            self._messages[session_id] = []
        self._messages[session_id].append(msg)
        return msg

    async def get_messages(self, session_id: uuid.UUID) -> list[InMemoryMessage]:
        return list(self._messages.get(session_id, []))

    async def update_profile(
        self, session_id: uuid.UUID, profile_data: dict[str, Any]
    ) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.profile_json = profile_data
        session.updated_at = datetime.now(tz=UTC)
        return True


# ---------------------------------------------------------------------------
# Fixture factory
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _integration_client(fake_provider: FakeLLMProvider, sm: InMemorySessionManager):
    """Build an httpx.AsyncClient wired to the real pipeline.

    - Noop lifespan (skips DB init)
    - _create_session_manager returns the given InMemorySessionManager instance
    - _create_agent_loop returns a real AgentLoop backed by FakeLLMProvider + real ToolRegistry
    """
    from kara_api.main import create_app

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    def _make_session_manager():
        return sm

    def _make_agent_loop(settings):
        client = LLMClient(fake_provider, system_prompt=ENHANCED_SYSTEM_PROMPT)
        registry = ToolRegistry()
        return AgentLoop(llm_client=client, tool_registry=registry)

    with (
        patch("kara_api.main.lifespan", _noop_lifespan),
        patch("kara_api.routers.chat._create_session_manager", _make_session_manager),
        patch("kara_api.routers.chat._create_agent_loop", _make_agent_loop),
    ):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Part 1: Single-Turn Integration Tests
# ---------------------------------------------------------------------------


class TestSingleTurnIntegration:
    """Verify that a single POST /api/v1/chat round-trips correctly through the
    real tool registry (FakeLLMProvider drives tool selection; tools are real).
    """

    # ------------------------------------------------------------------
    # Test 1: compute_tax → SSE stream
    # ------------------------------------------------------------------

    async def test_salary_tax_computation_sse(self):
        """FakeLLM calls compute_tax → real engine returns tax numbers → SSE stream."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "compute_tax",
                            {"gross_salary": 1500000, "regime": "new"},
                        )
                    ]
                ),
                _fake_response(
                    content="Your tax under the new regime is computed. Please review the breakdown."
                ),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post("/api/v1/chat", json={"message": "Compute my tax"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = parse_sse_events(resp.text)

        # Must start with session_created
        assert events[0]["type"] == "session_created"

        # tool_result event must carry real engine numbers
        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "compute_tax"
        assert tool_events[0]["is_error"] is False

        result_data = json.loads(tool_events[0]["result"])
        # The tax engine returns 'total_tax_payable' (not 'total_tax')
        assert "total_tax_payable" in result_data
        assert isinstance(result_data["total_tax_payable"], (int, float))
        assert result_data["total_tax_payable"] > 0

        # content arrives as streamed deltas
        deltas = [e for e in events if e["type"] == "content_delta"]
        assert len(deltas) >= 1
        full_text = "".join(e["text"] for e in deltas)
        assert "tax" in full_text.lower()

        # done event must close the stream
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    # ------------------------------------------------------------------
    # Test 2: compute_tax → JSON fallback
    # ------------------------------------------------------------------

    async def test_salary_tax_computation_json(self):
        """Same scenario via Accept: application/json returns structured JSON."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "compute_tax",
                            {"gross_salary": 1500000, "regime": "new"},
                        )
                    ]
                ),
                _fake_response(content="Tax computed under new regime."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post(
                "/api/v1/chat",
                json={"message": "Compute my tax"},
                headers={"Accept": "application/json"},
            )

        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

        data = resp.json()
        assert "session_id" in data
        assert "response" in data
        assert "tool_calls_made" in data
        assert "profile_state" in data

        # tool_calls_made should contain compute_tax with real result
        assert len(data["tool_calls_made"]) == 1
        tc = data["tool_calls_made"][0]
        assert tc["tool_name"] == "compute_tax"
        assert tc["is_error"] is False

        result_data = json.loads(tc["result"])
        # The tax engine returns 'total_tax_payable' (not 'total_tax')
        assert "total_tax_payable" in result_data
        assert result_data["total_tax_payable"] > 0

    # ------------------------------------------------------------------
    # Test 3: compare_regimes → advisory event fires
    # ------------------------------------------------------------------

    async def test_regime_comparison_flow(self):
        """compare_regimes triggers a real computation and an advisory hint."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "compare_regimes",
                            {
                                "gross_salary": 2000000,
                                "deductions": {"80C": 150000, "80D": 25000},
                            },
                        )
                    ]
                ),
                _fake_response(
                    content="Comparing old vs new regime for your income."
                ),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post("/api/v1/chat", json={"message": "Compare tax regimes"})

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        # compare_regimes tool result must have recommendation
        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "compare_regimes"
        assert tool_events[0]["is_error"] is False

        result_data = json.loads(tool_events[0]["result"])
        assert "recommended_regime" in result_data

        # advisory event fires (compare_regimes alone has an advisory)
        advisory_events = [e for e in events if e["type"] == "advisory"]
        assert len(advisory_events) >= 1
        assert "hint" in advisory_events[0]

    # ------------------------------------------------------------------
    # Test 4: compute_capital_gains → gain data returned
    # ------------------------------------------------------------------

    async def test_capital_gains_computation(self):
        """compute_capital_gains on an equity transaction returns gain data."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "compute_capital_gains",
                            {
                                "transactions": [
                                    {
                                        "asset_class": "listed_equity",
                                        "purchase_price": 500000,
                                        "sale_price": 800000,
                                        "holding_months": 14,
                                    }
                                ]
                            },
                        )
                    ]
                ),
                _fake_response(content="Your capital gains have been computed."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post("/api/v1/chat", json={"message": "Compute capital gains"})

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "compute_capital_gains"
        assert tool_events[0]["is_error"] is False

        result_data = json.loads(tool_events[0]["result"])
        # Returns a list of transaction results
        assert isinstance(result_data, list)
        assert len(result_data) == 1
        record = result_data[0]
        # CapitalGainsResult fields from the tax engine
        assert "total_gain" in record
        assert "taxable_gain" in record
        assert "tax_amount" in record
        assert "tax_rate" in record

    # ------------------------------------------------------------------
    # Test 5: find_deduction_gaps → optimization suggestions returned
    # ------------------------------------------------------------------

    async def test_deduction_optimization(self):
        """find_deduction_gaps returns suggestions for maximizing deductions."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "find_deduction_gaps",
                            {"gross_salary": 2000000},
                        )
                    ]
                ),
                _fake_response(content="Here are your deduction optimization suggestions."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post("/api/v1/chat", json={"message": "Optimize my deductions"})

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "find_deduction_gaps"
        assert tool_events[0]["is_error"] is False

        result_data = json.loads(tool_events[0]["result"])
        # Should return a dict with suggestions/gaps
        assert isinstance(result_data, dict)
        # At least one meaningful key should be present
        assert len(result_data) > 0

    # ------------------------------------------------------------------
    # Test 6: get_tds_rate stub
    # ------------------------------------------------------------------

    async def test_tds_rate_tool(self):
        """get_tds_rate returns section and rate information from the rate table."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "get_tds_rate",
                            {"payment_type": "salary"},
                        )
                    ]
                ),
                _fake_response(content="TDS on salary is deducted as per your income slab."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post("/api/v1/chat", json={"message": "What is TDS on salary?"})

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "get_tds_rate"
        assert tool_events[0]["is_error"] is False

        result_data = json.loads(tool_events[0]["result"])
        assert "section" in result_data
        assert result_data["section"] == "192"
        assert result_data["payment_type"] == "salary"

    # ------------------------------------------------------------------
    # Test 7: calculate_advance_tax stub
    # ------------------------------------------------------------------

    async def test_advance_tax_tool(self):
        """calculate_advance_tax returns the s.211 installment schedule."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "calculate_advance_tax",
                            {"total_estimated_tax": 200000},
                        )
                    ]
                ),
                _fake_response(content="Here is your advance tax installment schedule."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post(
                "/api/v1/chat", json={"message": "Calculate advance tax installments"}
            )

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "calculate_advance_tax"
        assert tool_events[0]["is_error"] is False

        result_data = json.loads(tool_events[0]["result"])
        assert result_data["required"] is True
        assert "installments" in result_data
        assert len(result_data["installments"]) == 4
        # Verify Q1 installment structure
        q1 = result_data["installments"][0]
        assert q1["quarter"] == "Q1"
        assert q1["due_date"] == "2025-06-15"
        assert q1["amount_due"] == 30000  # 15% of 200K

    # ------------------------------------------------------------------
    # Test 8: unknown tool → error in tool_result, then content
    # ------------------------------------------------------------------

    async def test_error_recovery_unknown_tool(self):
        """Calling a nonexistent tool produces is_error=True, then LLM recovers."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(
                    tool_calls=[
                        _tool_call("nonexistent_tool", {"some_arg": "value"})
                    ]
                ),
                _fake_response(
                    content="I couldn't use that tool. Let me answer directly."
                ),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post("/api/v1/chat", json={"message": "Use a weird tool"})

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        # tool_result event should indicate error
        tool_events = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_name"] == "nonexistent_tool"
        assert tool_events[0]["is_error"] is True
        assert "Unknown tool" in tool_events[0]["result"]

        # LLM still produces a final streamed response
        deltas = [e for e in events if e["type"] == "content_delta"]
        assert len("".join(e["text"] for e in deltas)) > 0

        # Stream ends with done
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1


# ---------------------------------------------------------------------------
# Part 2: Multi-Turn Integration Tests
# ---------------------------------------------------------------------------


class TestMultiTurnIntegration:
    """Verify that session state persists across multiple HTTP requests within
    the same test, using a shared InMemorySessionManager instance.
    """

    # ------------------------------------------------------------------
    # Test 1: create then continue session
    # ------------------------------------------------------------------

    async def test_create_then_continue_session(self):
        """POST /chat → extract session_id → POST /chat/{id} → GET /chat/{id}."""
        # Turn 1 — create session
        fake = FakeLLMProvider(
            responses=[
                # turn 1
                _fake_response(content="Hello! I am Kara, your tax advisor."),
                # turn 2
                _fake_response(content="Your tax under the new regime: approx Rs 1,12,500."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            # Turn 1: create new session
            resp1 = await ac.post("/api/v1/chat", json={"message": "Hello"})
            assert resp1.status_code == 200
            events1 = parse_sse_events(resp1.text)
            session_created = [e for e in events1 if e["type"] == "session_created"]
            assert len(session_created) == 1
            session_id = session_created[0]["session_id"]

            # Turn 2: continue the session
            resp2 = await ac.post(
                f"/api/v1/chat/{session_id}",
                json={"message": "What is my tax?"},
            )
            assert resp2.status_code == 200

            # GET session history
            resp3 = await ac.get(f"/api/v1/chat/{session_id}")
            assert resp3.status_code == 200
            history_data = resp3.json()
            assert history_data["session_id"] == session_id
            assert len(history_data["messages"]) >= 2  # user + assistant from turn 1

    # ------------------------------------------------------------------
    # Test 2: profile accumulates across turns
    # ------------------------------------------------------------------

    async def test_profile_accumulates_across_turns(self):
        """Profile snapshot from turn 1 is persisted and read back in GET session."""
        fake = FakeLLMProvider(
            responses=[
                # turn 1: tool call + text
                _fake_response(
                    tool_calls=[
                        _tool_call(
                            "compute_tax",
                            {"gross_salary": 1200000, "regime": "new"},
                        )
                    ]
                ),
                _fake_response(content="Tax computed for Rs 12L income."),
                # turn 2: plain text
                _fake_response(content="Your profile shows salary income."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            # Turn 1
            resp1 = await ac.post(
                "/api/v1/chat", json={"message": "What is my tax on 12 lakh?"}
            )
            assert resp1.status_code == 200
            events1 = parse_sse_events(resp1.text)
            session_id = [e for e in events1 if e["type"] == "session_created"][0]["session_id"]

            # Turn 2
            resp2 = await ac.post(
                f"/api/v1/chat/{session_id}",
                json={"message": "What can I tell you about my income?"},
            )
            assert resp2.status_code == 200

            # Verify session and messages exist
            resp3 = await ac.get(f"/api/v1/chat/{session_id}")
            assert resp3.status_code == 200
            data = resp3.json()
            assert "profile_state" in data
            # profile_state is a dict with slots and ready_intents
            assert "slots" in data["profile_state"]
            assert "ready_intents" in data["profile_state"]

    # ------------------------------------------------------------------
    # Test 3: session deletion
    # ------------------------------------------------------------------

    async def test_session_deletion(self):
        """Create a session, delete it, then GET returns 404."""
        fake = FakeLLMProvider(
            responses=[
                _fake_response(content="Session created successfully."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            # Create
            resp1 = await ac.post("/api/v1/chat", json={"message": "Start"})
            assert resp1.status_code == 200
            events = parse_sse_events(resp1.text)
            session_id = [e for e in events if e["type"] == "session_created"][0]["session_id"]

            # Delete
            resp2 = await ac.delete(f"/api/v1/chat/{session_id}")
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "deleted"

            # GET should now 404
            resp3 = await ac.get(f"/api/v1/chat/{session_id}")
            assert resp3.status_code == 404

    # ------------------------------------------------------------------
    # Test 4: continue nonexistent session → 404
    # ------------------------------------------------------------------

    async def test_continue_nonexistent_session_404(self):
        """POST to /api/v1/chat/{random-uuid} returns 404."""
        fake = FakeLLMProvider()
        sm = InMemorySessionManager()
        random_id = uuid.uuid4()

        async with _integration_client(fake, sm) as ac:
            resp = await ac.post(
                f"/api/v1/chat/{random_id}",
                json={"message": "Hello?"},
            )

        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # Test 5: history forwarded to agent
    # ------------------------------------------------------------------

    async def test_history_forwarded_to_agent(self):
        """On turn 2, FakeLLMProvider.last_request includes prior messages."""
        fake = FakeLLMProvider(
            responses=[
                # turn 1
                _fake_response(content="Hi! I am Kara."),
                # turn 2
                _fake_response(content="Sure, I remember your earlier question."),
            ]
        )
        sm = InMemorySessionManager()

        async with _integration_client(fake, sm) as ac:
            # Turn 1
            resp1 = await ac.post("/api/v1/chat", json={"message": "Hello, Kara!"})
            assert resp1.status_code == 200
            events1 = parse_sse_events(resp1.text)
            session_id = [e for e in events1 if e["type"] == "session_created"][0]["session_id"]

            # Turn 2
            resp2 = await ac.post(
                f"/api/v1/chat/{session_id}",
                json={"message": "Do you remember me?"},
            )
            assert resp2.status_code == 200

        # last_request on turn 2 should include the history from turn 1
        # The request messages include: system + prior user + prior assistant + new user
        assert fake.last_request is not None
        message_roles = [m.role for m in fake.last_request.messages]
        # Role is a str enum, so direct comparison works
        assert Role.system in message_roles, "system message should be present"
        assert message_roles[0] == Role.system, "system message should be first"
        # There should be more than 2 messages (system + user only)
        assert len(fake.last_request.messages) > 2
