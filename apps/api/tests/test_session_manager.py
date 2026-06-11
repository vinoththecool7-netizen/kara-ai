"""Unit tests for kara_api.agent.session — SessionManager with mocked async DB."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from kara_api.agent.session import SessionManager, SessionSummaryRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_factory():
    """Return (mock_factory, mock_db) where mock_factory() yields mock_db as async ctx."""
    mock_db = AsyncMock()
    # db.add() and db.delete() are synchronous in SQLAlchemy — use plain MagicMock
    # to avoid "coroutine never awaited" warnings.
    mock_db.add = MagicMock()
    mock_factory = MagicMock()
    # async context manager: factory() returns ctx that yields mock_db
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_factory, mock_db


def _make_fake_session(session_id: uuid.UUID | None = None, profile_json=None):
    """Create a lightweight fake DbSession object."""
    fake = MagicMock()
    fake.id = session_id or uuid.uuid4()
    fake.profile_json = profile_json or {}
    return fake


def _make_fake_message(
    session_id: uuid.UUID,
    role: str = "user",
    content: str = "hello",
    tool_calls_json=None,
    msg_id: int = 1,
):
    """Create a lightweight fake DbMessage object."""
    fake = MagicMock()
    fake.id = msg_id
    fake.session_id = session_id
    fake.role = role
    fake.content = content
    fake.tool_calls_json = tool_calls_json
    return fake


# ---------------------------------------------------------------------------
# TestCreateSession
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for SessionManager.create_session."""

    async def test_create_session_returns_uuid(self):
        """create_session returns a UUID from the persisted DbSession."""
        expected_id = uuid.uuid4()
        mock_factory, mock_db = _make_mock_factory()

        # After refresh, session.id should be set
        async def _set_id(obj):
            obj.id = expected_id

        mock_db.refresh.side_effect = _set_id

        mgr = SessionManager(mock_factory)
        result = await mgr.create_session()

        assert result == expected_id
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    async def test_create_session_with_profile(self):
        """profile_data is forwarded to DbSession constructor."""
        mock_factory, mock_db = _make_mock_factory()

        async def _set_id(obj):
            obj.id = uuid.uuid4()

        mock_db.refresh.side_effect = _set_id

        mgr = SessionManager(mock_factory)
        profile = {"regime": "new", "gross_salary": 1500000}

        with patch("kara_api.agent.session.DbSession") as MockDbSession:
            mock_instance = MagicMock()
            mock_instance.id = uuid.uuid4()
            MockDbSession.return_value = mock_instance
            mock_db.refresh.side_effect = None  # no-op

            await mgr.create_session(profile_data=profile)

            MockDbSession.assert_called_once_with(profile_json=profile)

    async def test_create_session_default_profile(self):
        """When profile_data is None, an empty dict is used."""
        mock_factory, mock_db = _make_mock_factory()

        with patch("kara_api.agent.session.DbSession") as MockDbSession:
            mock_instance = MagicMock()
            mock_instance.id = uuid.uuid4()
            MockDbSession.return_value = mock_instance

            mgr = SessionManager(mock_factory)
            await mgr.create_session(profile_data=None)

            MockDbSession.assert_called_once_with(profile_json={})


# ---------------------------------------------------------------------------
# TestGetSession
# ---------------------------------------------------------------------------


class TestGetSession:
    """Tests for SessionManager.get_session."""

    async def test_get_existing_session(self):
        """db.get returns a session; verify it's returned as-is."""
        mock_factory, mock_db = _make_mock_factory()
        expected = _make_fake_session()
        mock_db.get.return_value = expected

        mgr = SessionManager(mock_factory)
        result = await mgr.get_session(expected.id)

        assert result is expected

    async def test_get_nonexistent_returns_none(self):
        """db.get returns None for unknown session_id."""
        mock_factory, mock_db = _make_mock_factory()
        mock_db.get.return_value = None

        mgr = SessionManager(mock_factory)
        result = await mgr.get_session(uuid.uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# TestDeleteSession
# ---------------------------------------------------------------------------


class TestDeleteSession:
    """Tests for SessionManager.delete_session."""

    async def test_delete_existing_returns_true(self):
        """Session found -> delete + commit -> True."""
        mock_factory, mock_db = _make_mock_factory()
        fake_session = _make_fake_session()
        mock_db.get.return_value = fake_session

        mgr = SessionManager(mock_factory)
        result = await mgr.delete_session(fake_session.id)

        assert result is True
        mock_db.delete.assert_awaited_once_with(fake_session)
        mock_db.commit.assert_awaited_once()

    async def test_delete_nonexistent_returns_false(self):
        """Session not found -> False, no delete/commit."""
        mock_factory, mock_db = _make_mock_factory()
        mock_db.get.return_value = None

        mgr = SessionManager(mock_factory)
        result = await mgr.delete_session(uuid.uuid4())

        assert result is False
        mock_db.delete.assert_not_awaited()
        mock_db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestAddMessage
# ---------------------------------------------------------------------------


class TestAddMessage:
    """Tests for SessionManager.add_message."""

    async def test_add_message_persists(self):
        """Message created with correct fields, persisted via add+commit+refresh."""
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()

        with patch("kara_api.agent.session.DbMessage") as MockDbMessage:
            mock_msg = MagicMock()
            MockDbMessage.return_value = mock_msg

            mgr = SessionManager(mock_factory)
            result = await mgr.add_message(sid, "user", "What is 80C?")

            MockDbMessage.assert_called_once_with(
                session_id=sid,
                role="user",
                content="What is 80C?",
                tool_calls_json=None,
            )
            mock_db.add.assert_called_once_with(mock_msg)
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(mock_msg)
            assert result is mock_msg

    async def test_add_message_with_tool_calls(self):
        """tool_calls_json is populated when tool_calls argument is provided."""
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()
        tool_calls = [{"id": "call_1", "name": "compute_tax", "arguments": {"regime": "new"}}]

        with patch("kara_api.agent.session.DbMessage") as MockDbMessage:
            mock_msg = MagicMock()
            MockDbMessage.return_value = mock_msg

            mgr = SessionManager(mock_factory)
            await mgr.add_message(sid, "assistant", None, tool_calls=tool_calls)

            MockDbMessage.assert_called_once_with(
                session_id=sid,
                role="assistant",
                content=None,
                tool_calls_json=tool_calls,
            )


# ---------------------------------------------------------------------------
# TestUpdateProfile
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """Tests for SessionManager.update_profile."""

    async def test_update_existing_returns_true(self):
        """Session found -> profile_json updated, committed -> True."""
        mock_factory, mock_db = _make_mock_factory()
        fake_session = _make_fake_session(profile_json={})
        mock_db.get.return_value = fake_session

        new_profile = {"regime": "old", "age_category": "senior"}
        mgr = SessionManager(mock_factory)
        result = await mgr.update_profile(fake_session.id, new_profile)

        assert result is True
        assert fake_session.profile_json == new_profile
        mock_db.commit.assert_awaited_once()

    async def test_update_nonexistent_returns_false(self):
        """Session not found -> False, no commit."""
        mock_factory, mock_db = _make_mock_factory()
        mock_db.get.return_value = None

        mgr = SessionManager(mock_factory)
        result = await mgr.update_profile(uuid.uuid4(), {"foo": "bar"})

        assert result is False
        mock_db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestListSessions
# ---------------------------------------------------------------------------


def _make_scalars_result(items):
    """Wrap items as a MagicMock that mimics ``result.scalars().all()``."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = items
    return mock_result


def _make_dated_fake_session(
    session_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
):
    fake = _make_fake_session(session_id=session_id)
    ts = created_at or datetime(2026, 4, 8, 10, 0, 0, tzinfo=UTC)
    fake.created_at = ts
    fake.updated_at = updated_at or ts
    return fake


def _make_rows_result(rows):
    """Mock result whose .all() returns plain row tuples."""
    res = MagicMock()
    res.all.return_value = rows
    return res


def _wire_list_queries(mock_db, sessions, counts=None, first_user_messages=None):
    """Wire the three fixed queries list_sessions now issues:

    1. sessions (scalars)   2. counts (session_id, n)   3. first user msgs
    """
    side_effects = [_make_scalars_result(sessions)]
    if sessions:
        side_effects.append(_make_rows_result(list((counts or {}).items())))
        side_effects.append(_make_rows_result(list((first_user_messages or {}).items())))
    mock_db.execute = AsyncMock(side_effect=side_effects)


class TestListSessions:
    """Tests for SessionManager.list_sessions (fixed 3-query shape, no N+1)."""

    async def test_list_sessions_empty(self):
        """No sessions -> empty list, and only ONE query is issued."""
        mock_factory, mock_db = _make_mock_factory()
        _wire_list_queries(mock_db, [])

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert result == []
        assert mock_db.execute.await_count == 1

    async def test_query_count_is_constant_regardless_of_sessions(self):
        """The N+1 is gone: 3 queries whether there is 1 session or 50."""
        mock_factory, mock_db = _make_mock_factory()
        sessions = [
            _make_dated_fake_session(
                session_id=uuid.uuid4(),
                updated_at=datetime(2026, 4, 8, 12, 0, i, tzinfo=UTC),
            )
            for i in range(50)
        ]
        _wire_list_queries(mock_db, sessions)

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert len(result) == 50
        assert mock_db.execute.await_count == 3

    async def test_list_sessions_sorted_order_preserved(self):
        """Sorting is delegated to SQL; rows come back in query order."""
        mock_factory, mock_db = _make_mock_factory()
        sid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        sid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        newer = _make_dated_fake_session(
            session_id=sid1,
            updated_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC),
        )
        older = _make_dated_fake_session(
            session_id=sid2,
            updated_at=datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC),
        )
        _wire_list_queries(mock_db, [newer, older])

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert [r.id for r in result] == [str(sid1), str(sid2)]

    async def test_list_sessions_title_from_first_user_message(self):
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()
        sess = _make_dated_fake_session(session_id=sid)
        _wire_list_queries(
            mock_db,
            [sess],
            counts={sid: 1},
            first_user_messages={sid: "How much tax on 15 LPA?"},
        )

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert result[0].title == "How much tax on 15 LPA?"
        assert result[0].message_count == 1

    async def test_list_sessions_title_truncates_at_60_chars(self):
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()
        sess = _make_dated_fake_session(session_id=sid)
        _wire_list_queries(
            mock_db, [sess], counts={sid: 1}, first_user_messages={sid: "a" * 100}
        )

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert len(result[0].title) == 61  # 60 chars + ellipsis
        assert result[0].title.endswith("…")

    async def test_list_sessions_title_fallback_when_no_messages(self):
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()
        sess = _make_dated_fake_session(session_id=sid)
        _wire_list_queries(mock_db, [sess])

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert result[0].title == "New Chat"
        assert result[0].message_count == 0

    async def test_list_sessions_count_without_user_message(self):
        """Assistant-only sessions still report their message count."""
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()
        sess = _make_dated_fake_session(session_id=sid)
        _wire_list_queries(mock_db, [sess], counts={sid: 1})

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert result[0].title == "New Chat"
        assert result[0].message_count == 1

    async def test_list_sessions_returns_summary_dataclass(self):
        mock_factory, mock_db = _make_mock_factory()
        sid = uuid.uuid4()
        sess = _make_dated_fake_session(session_id=sid)
        _wire_list_queries(mock_db, [sess])

        mgr = SessionManager(mock_factory)
        result = await mgr.list_sessions()

        assert isinstance(result[0], SessionSummaryRow)
        assert result[0].id == str(sid)
        assert result[0].created_at == sess.created_at
        assert result[0].updated_at == sess.updated_at


class TestDeleteSessionsOlderThan:
    async def test_deletes_and_returns_rowcount(self):
        mock_factory, mock_db = _make_mock_factory()
        result = MagicMock()
        result.rowcount = 7
        mock_db.execute = AsyncMock(return_value=result)

        mgr = SessionManager(mock_factory)
        deleted = await mgr.delete_sessions_older_than(30)

        assert deleted == 7
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    async def test_zero_days_is_rejected(self):
        mock_factory, _ = _make_mock_factory()
        mgr = SessionManager(mock_factory)
        try:
            await mgr.delete_sessions_older_than(0)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
