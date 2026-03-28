"""Hybrid search module for Kara knowledge retrieval.

Combines semantic search (pgvector cosine similarity), keyword search
(PostgreSQL full-text search via tsvector), and graph boost (ltree + section
relationships) using Reciprocal Rank Fusion (RRF) to return the most relevant
tax sections for a given user query.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from kara_api.knowledge.embeddings import EmbeddingProvider

__all__ = [
    "SearchResult",
    "semantic_search",
    "keyword_search",
    "graph_boost",
    "hybrid_search",
]

RRF_K = 60  # standard RRF constant from Cormack et al. 2009


class SearchResult(BaseModel):
    id: int
    section_number: str
    title: str
    summary: str | None = None
    score: float = 0.0


async def semantic_search(
    query: str,
    k: int,
    session: AsyncSession,
    provider: EmbeddingProvider,
) -> list[SearchResult]:
    """Search tax sections by semantic similarity using pgvector cosine distance.

    Embeds the query text and finds the nearest neighbours in the embedding
    space, returning sections ordered by descending cosine similarity score.
    """
    query_embedding = await provider.embed_single(query)

    sql = text(
        """
        SELECT id, section_number, title, summary,
               1 - (embedding <=> :embedding::vector) AS score
        FROM tax_sections
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :embedding::vector
        LIMIT :k
        """
    )
    result = await session.execute(
        sql,
        {"embedding": str(query_embedding), "k": k},
    )
    rows = result.fetchall()
    return [
        SearchResult(
            id=row.id,
            section_number=row.section_number,
            title=row.title,
            summary=row.summary,
            score=float(row.score),
        )
        for row in rows
    ]


async def keyword_search(
    query: str,
    k: int,
    session: AsyncSession,
) -> list[SearchResult]:
    """Search tax sections using PostgreSQL full-text search (tsvector/tsquery).

    Uses plainto_tsquery which is safe for raw user input — no special syntax
    knowledge is required from the user and malformed queries cannot cause
    errors.
    """
    sql = text(
        """
        SELECT id, section_number, title, summary,
               ts_rank(search_vector, plainto_tsquery('english', :query)) AS score
        FROM tax_sections
        WHERE search_vector @@ plainto_tsquery('english', :query)
        ORDER BY score DESC
        LIMIT :k
        """
    )
    result = await session.execute(sql, {"query": query, "k": k})
    rows = result.fetchall()
    return [
        SearchResult(
            id=row.id,
            section_number=row.section_number,
            title=row.title,
            summary=row.summary,
            score=float(row.score),
        )
        for row in rows
    ]


async def graph_boost(
    section_ids: list[int],
    session: AsyncSession,
) -> dict[int, float]:
    """Find sections related to the candidate set and return boost scores.

    Explores two sources of relatedness:
    - Direct relationships recorded in ``section_relationships`` (boost 0.3)
    - ltree siblings — sections sharing the same parent path (boost 0.1)

    Only sections that are NOT already in ``section_ids`` are returned so the
    caller can safely add these boosts to entirely new candidates without
    double-counting existing ones.

    Returns a mapping of section_id -> boost_score.
    """
    if not section_ids:
        return {}

    id_set = set(section_ids)
    boost_map: dict[int, float] = {}

    # --- Direct relationships ---
    rel_sql = text(
        """
        SELECT DISTINCT CASE
          WHEN parent_id = ANY(:ids) THEN child_id
          ELSE parent_id
        END AS related_id
        FROM section_relationships
        WHERE parent_id = ANY(:ids) OR child_id = ANY(:ids)
        """
    )
    rel_result = await session.execute(rel_sql, {"ids": section_ids})
    for row in rel_result.fetchall():
        rid = row.related_id
        if rid not in id_set:
            boost_map[rid] = max(boost_map.get(rid, 0.0), 0.3)

    # --- ltree siblings ---
    sibling_sql = text(
        """
        SELECT DISTINCT t2.id
        FROM tax_sections t1
        JOIN tax_sections t2 ON
          t2.ltree_path::ltree <@ subpath(t1.ltree_path::ltree, 0, nlevel(t1.ltree_path::ltree) - 1)
          AND t2.id != t1.id
        WHERE t1.id = ANY(:ids)
        LIMIT 20
        """
    )
    sib_result = await session.execute(sibling_sql, {"ids": section_ids})
    for row in sib_result.fetchall():
        sid = row.id
        if sid not in id_set:
            # Only set sibling boost if no stronger boost already exists
            if boost_map.get(sid, 0.0) < 0.1:
                boost_map[sid] = 0.1

    return boost_map


async def hybrid_search(
    query: str,
    k: int,
    session: AsyncSession,
    provider: EmbeddingProvider,
) -> list[SearchResult]:
    """Retrieve the top-k tax sections most relevant to ``query``.

    Combines semantic search, keyword search, and graph boost via Reciprocal
    Rank Fusion (RRF).  Semantic and keyword searches run concurrently; graph
    boost is applied to the top candidates of their fusion to surface closely
    related sections that might otherwise be missed.
    """
    fetch_k = min(k * 3, 50)  # over-fetch for better fusion

    # Run semantic and keyword searches concurrently
    semantic_results, keyword_results = await asyncio.gather(
        semantic_search(query, fetch_k, session, provider),
        keyword_search(query, fetch_k, session),
    )

    # Build RRF scores and result map
    rrf_scores: dict[int, float] = {}
    result_map: dict[int, SearchResult] = {}

    for rank, r in enumerate(semantic_results):
        rrf_scores[r.id] = rrf_scores.get(r.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        result_map[r.id] = r

    for rank, r in enumerate(keyword_results):
        rrf_scores[r.id] = rrf_scores.get(r.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        if r.id not in result_map:
            result_map[r.id] = r

    # Apply graph boost to top candidates
    top_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]  # type: ignore[arg-type]
    boost_map = await graph_boost(top_ids, session)

    for sid, boost in boost_map.items():
        rrf_scores[sid] = rrf_scores.get(sid, 0.0) + boost / (RRF_K + 1)
        # Fetch boosted section metadata if not already cached
        if sid not in result_map:
            row_result = await session.execute(
                text("SELECT id, section_number, title, summary FROM tax_sections WHERE id = :id"),
                {"id": sid},
            )
            r = row_result.fetchone()
            if r:
                result_map[sid] = SearchResult(
                    id=r.id,
                    section_number=r.section_number,
                    title=r.title,
                    summary=r.summary,
                    score=0.0,
                )

    # Sort by final RRF score and return top k
    final_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]  # type: ignore[arg-type]
    results = []
    for sid in final_ids:
        if sid in result_map:
            r = result_map[sid]
            r = r.model_copy(update={"score": rrf_scores[sid]})
            results.append(r)

    return results
