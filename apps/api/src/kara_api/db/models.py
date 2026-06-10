"""SQLAlchemy 2.0 declarative models for Kara."""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import Computed

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RelationshipType(str, enum.Enum):
    OVERRIDES = "overrides"
    SUPPLEMENTS = "supplements"
    REQUIRES = "requires"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tax Sections
# ---------------------------------------------------------------------------


class TaxSection(Base):
    __tablename__ = "tax_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ltree_path: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title, '') || ' ' || "
            "coalesce(content, '') || ' ' || coalesce(summary, ''))",
            persisted=True,
        ),
        nullable=True,
    )
    metadata_json = mapped_column(JSONB, nullable=True, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    parent_relationships: Mapped[list["SectionRelationship"]] = relationship(
        "SectionRelationship",
        foreign_keys="SectionRelationship.parent_id",
        back_populates="parent",
    )
    child_relationships: Mapped[list["SectionRelationship"]] = relationship(
        "SectionRelationship",
        foreign_keys="SectionRelationship.child_id",
        back_populates="child",
    )


# ---------------------------------------------------------------------------
# Section Relationships
# ---------------------------------------------------------------------------


class SectionRelationship(Base):
    __tablename__ = "section_relationships"
    __table_args__ = (
        UniqueConstraint(
            "parent_id", "child_id", "relationship_type", name="uq_section_relationship"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tax_sections.id", ondelete="CASCADE"), nullable=False
    )
    child_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tax_sections.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    parent: Mapped["TaxSection"] = relationship(
        "TaxSection", foreign_keys=[parent_id], back_populates="parent_relationships"
    )
    child: Mapped["TaxSection"] = relationship(
        "TaxSection", foreign_keys=[child_id], back_populates="child_relationships"
    )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    profile_json = mapped_column(JSONB, nullable=True, server_default="{}")

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls_json = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
