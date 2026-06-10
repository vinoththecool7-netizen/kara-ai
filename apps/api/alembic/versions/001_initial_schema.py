"""Initial schema -- tax_sections, section_relationships, sessions, messages

Revision ID: 001
Revises:
Create Date: 2026-03-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable required PostgreSQL extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")

    # ── tax_sections ──────────────────────────────────────────────────────
    op.create_table(
        "tax_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("section_number", sa.String(100), unique=True, nullable=False),
        sa.Column("ltree_path", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' "
                "|| coalesce(content, '') || ' ' || coalesce(summary, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("metadata_json", JSONB(), nullable=True, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── section_relationships ─────────────────────────────────────────────
    op.create_table(
        "section_relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("tax_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_id",
            sa.Integer(),
            sa.ForeignKey("tax_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "parent_id",
            "child_id",
            "relationship_type",
            name="uq_section_relationship",
        ),
    )

    # ── sessions ──────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("profile_json", JSONB(), nullable=True, server_default="{}"),
    )

    # ── messages ──────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_calls_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── Indexes ───────────────────────────────────────────────────────────

    # GIN index on search_vector for full-text search
    op.create_index(
        "ix_tax_sections_search_vector",
        "tax_sections",
        ["search_vector"],
        postgresql_using="gin",
    )

    # GiST index on ltree_path for hierarchical queries (CAST avoids asyncpg :: issue)
    op.execute(
        "CREATE INDEX ix_tax_sections_ltree_path "
        "ON tax_sections USING gist (CAST(ltree_path AS ltree))"
    )

    # HNSW index on embedding for vector similarity search
    op.execute(
        "CREATE INDEX ix_tax_sections_embedding "
        "ON tax_sections "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # Composite B-tree on messages for session history queries
    op.create_index(
        "ix_messages_session_created",
        "messages",
        ["session_id", "created_at"],
    )

    # B-tree on sessions.updated_at for cleanup / sorting
    op.create_index(
        "ix_sessions_updated_at",
        "sessions",
        ["updated_at"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_sessions_updated_at")
    op.drop_index("ix_messages_session_created")
    op.execute("DROP INDEX IF EXISTS ix_tax_sections_embedding")
    op.execute("DROP INDEX IF EXISTS ix_tax_sections_ltree_path")
    op.drop_index("ix_tax_sections_search_vector")

    # Drop tables (reverse dependency order)
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("section_relationships")
    op.drop_table("tax_sections")

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS ltree")
    op.execute("DROP EXTENSION IF EXISTS vector")
