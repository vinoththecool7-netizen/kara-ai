"""Session management: CRUD for chat sessions and message persistence."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kara_api.db.models import Message as DbMessage
from kara_api.db.models import Session as DbSession


@dataclass
class SessionSummaryRow:
    """Lightweight projection of a session for sidebar listing.

    ``title`` is derived from the first user message (truncated to 60 chars
    with an ellipsis, or ``"New Chat"`` when no user message exists).
    """

    id: str
    created_at: datetime
    updated_at: datetime
    title: str
    message_count: int


class SessionManager:
    """CRUD operations for chat sessions backed by PostgreSQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._factory = session_factory

    async def create_session(self, profile_data: dict[str, Any] | None = None) -> uuid.UUID:
        """Create a new chat session. Returns its UUID."""
        async with self._factory() as db:
            session = DbSession(profile_json=profile_data or {})
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session.id

    async def get_session(self, session_id: uuid.UUID) -> DbSession | None:
        """Fetch a session by ID. Returns None if not found."""
        async with self._factory() as db:
            return await db.get(DbSession, session_id)

    async def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session and all its messages (cascade). Returns True if found and deleted."""
        async with self._factory() as db:
            session = await db.get(DbSession, session_id)
            if session is None:
                return False
            await db.delete(session)
            await db.commit()
            return True

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str | None,
        tool_calls: list[dict] | None = None,
    ) -> DbMessage:
        """Persist a message to the given session."""
        async with self._factory() as db:
            msg = DbMessage(
                session_id=session_id,
                role=role,
                content=content,
                tool_calls_json=tool_calls,
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            return msg

    async def get_messages(self, session_id: uuid.UUID) -> list[DbMessage]:
        """Fetch all messages for a session, ordered by id (chronological)."""
        async with self._factory() as db:
            result = await db.execute(
                select(DbMessage)
                .where(DbMessage.session_id == session_id)
                .order_by(DbMessage.id)
            )
            return list(result.scalars().all())

    async def update_profile(self, session_id: uuid.UUID, profile_data: dict[str, Any]) -> bool:
        """Update the profile_json on a session. Returns True if session found."""
        async with self._factory() as db:
            session = await db.get(DbSession, session_id)
            if session is None:
                return False
            session.profile_json = profile_data
            await db.commit()
            return True

    async def delete_sessions_older_than(self, days: int) -> int:
        """Delete sessions (and their messages, via FK cascade) not updated
        in the last *days* days. Returns the number of sessions removed."""
        if days <= 0:
            raise ValueError("days must be positive; use SESSION_TTL_DAYS=0 to disable")
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        async with self._factory() as db:
            result = await db.execute(
                delete(DbSession).where(DbSession.updated_at < cutoff)
            )
            await db.commit()
            return result.rowcount or 0

    async def list_sessions(self) -> list[SessionSummaryRow]:
        """Return a summary of every session, newest first.

        Each row carries a derived ``title`` (the first user message, truncated
        to 60 characters with an ellipsis, or ``"New Chat"`` when the session
        has no user message yet) and a total ``message_count``.

        Issues a constant three queries regardless of the number of sessions
        (sessions, message counts, first user message per session).
        """
        async with self._factory() as db:
            sessions_result = await db.execute(
                select(DbSession).order_by(DbSession.updated_at.desc())
            )
            sessions = list(sessions_result.scalars().all())
            if not sessions:
                return []

            counts_result = await db.execute(
                select(DbMessage.session_id, func.count(DbMessage.id)).group_by(
                    DbMessage.session_id
                )
            )
            counts: dict[uuid.UUID, int] = dict(counts_result.all())

            first_user_msg_ids = (
                select(func.min(DbMessage.id))
                .where(DbMessage.role == "user")
                .group_by(DbMessage.session_id)
                .scalar_subquery()
            )
            titles_result = await db.execute(
                select(DbMessage.session_id, DbMessage.content).where(
                    DbMessage.id.in_(first_user_msg_ids)
                )
            )
            first_messages: dict[uuid.UUID, str | None] = dict(titles_result.all())

            summaries: list[SessionSummaryRow] = []
            for sess in sessions:
                raw_content = first_messages.get(sess.id) or ""
                if not raw_content:
                    title = "New Chat"
                elif len(raw_content) > 60:
                    title = raw_content[:60] + "…"
                else:
                    title = raw_content

                summaries.append(
                    SessionSummaryRow(
                        id=str(sess.id),
                        created_at=sess.created_at,
                        updated_at=sess.updated_at,
                        title=title,
                        message_count=counts.get(sess.id, 0),
                    )
                )
            return summaries
