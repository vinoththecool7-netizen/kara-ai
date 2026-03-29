"""Session management: CRUD for chat sessions and message persistence."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kara_api.db.models import Message as DbMessage, Session as DbSession


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
