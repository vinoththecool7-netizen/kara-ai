"""Tests for the hybrid search module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kara_api.knowledge.search import (
    SearchResult,
    semantic_search,
    keyword_search,
    graph_boost,
    hybrid_search,
    RRF_K,
)
from kara_api.knowledge.embeddings import FakeEmbeddingProvider


def _make_result(id: int, section_number: str = "TEST", title: str = "Test", score: float = 0.5) -> SearchResult:
    return SearchResult(id=id, section_number=section_number, title=title, score=score)


def _make_row(id, section_number, title, summary, score):
    """Create a mock row with named attributes."""
    row = MagicMock()
    row.id = id
    row.section_number = section_number
    row.title = title
    row.summary = summary
    row.score = score
    return row


class TestSearchResult:
    def test_model_has_expected_fields(self):
        r = SearchResult(id=1, section_number="80C", title="Section 80C")
        assert r.id == 1
        assert r.section_number == "80C"
        assert r.title == "Section 80C"
        assert r.summary is None
        assert r.score == 0.0

    def test_score_is_float(self):
        r = SearchResult(id=1, section_number="X", title="Y", score=1.5)
        assert isinstance(r.score, float)


class TestSemanticSearch:
    async def test_calls_embed_single(self):
        provider = AsyncMock()
        provider.embed_single.return_value = [0.1] * 1536
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        await semantic_search("test query", 5, session, provider)
        provider.embed_single.assert_called_once_with("test query")

    async def test_returns_search_results(self):
        provider = AsyncMock()
        provider.embed_single.return_value = [0.1] * 1536
        session = AsyncMock()
        mock_result = MagicMock()
        rows = [_make_row(1, "80C", "Section 80C", "Summary", 0.95)]
        mock_result.fetchall.return_value = rows
        session.execute.return_value = mock_result

        results = await semantic_search("deduction", 5, session, provider)
        assert len(results) == 1
        assert results[0].section_number == "80C"
        assert results[0].score == 0.95


class TestKeywordSearch:
    async def test_returns_matching_sections(self):
        session = AsyncMock()
        mock_result = MagicMock()
        rows = [_make_row(2, "80D", "Section 80D", "Health", 0.8)]
        mock_result.fetchall.return_value = rows
        session.execute.return_value = mock_result

        results = await keyword_search("health insurance", 5, session)
        assert len(results) == 1
        assert results[0].section_number == "80D"

    async def test_empty_results_for_no_match(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        results = await keyword_search("xyznonexistent", 5, session)
        assert results == []


class TestGraphBoost:
    async def test_empty_ids_returns_empty(self):
        session = AsyncMock()
        result = await graph_boost([], session)
        assert result == {}

    async def test_returns_boost_scores(self):
        session = AsyncMock()

        # Mock direct relationships query
        rel_result = MagicMock()
        rel_row = MagicMock()
        rel_row.related_id = 99
        rel_result.fetchall.return_value = [rel_row]

        # Mock ltree siblings query
        sib_result = MagicMock()
        sib_result.fetchall.return_value = []

        session.execute.side_effect = [rel_result, sib_result]

        result = await graph_boost([1, 2], session)
        assert 99 in result
        assert result[99] == 0.3  # direct relationship boost


class TestHybridSearch:
    async def test_returns_at_most_k_results(self):
        """hybrid_search should return at most k results."""
        provider = AsyncMock()
        provider.embed_single.return_value = [0.1] * 1536
        session = AsyncMock()

        # Create enough mock results
        semantic_rows = [_make_row(i, f"S{i}", f"Title {i}", None, 0.9 - i * 0.01) for i in range(10)]
        keyword_rows = [_make_row(i + 10, f"K{i}", f"KTitle {i}", None, 0.8 - i * 0.01) for i in range(10)]

        # graph boost returns empty (no relationships)
        graph_result = MagicMock()
        graph_result.fetchall.return_value = []

        call_count = 0
        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_r = MagicMock()
            if call_count == 1:  # semantic
                mock_r.fetchall.return_value = semantic_rows
            elif call_count == 2:  # keyword
                mock_r.fetchall.return_value = keyword_rows
            else:  # graph boost queries
                mock_r.fetchall.return_value = []
            return mock_r

        session.execute = AsyncMock(side_effect=mock_execute)

        results = await hybrid_search("test", 3, session, provider)
        assert len(results) <= 3

    async def test_rrf_boosts_overlap(self):
        """A document in both semantic and keyword results should score higher."""
        provider = AsyncMock()
        provider.embed_single.return_value = [0.1] * 1536
        session = AsyncMock()

        # Section id=1 appears in both, id=2 only in semantic, id=3 only in keyword
        semantic_rows = [
            _make_row(1, "OVERLAP", "Overlap", None, 0.9),
            _make_row(2, "SEM_ONLY", "Semantic Only", None, 0.8),
        ]
        keyword_rows = [
            _make_row(1, "OVERLAP", "Overlap", None, 0.7),
            _make_row(3, "KW_ONLY", "Keyword Only", None, 0.6),
        ]

        call_count = 0
        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_r = MagicMock()
            if call_count == 1:
                mock_r.fetchall.return_value = semantic_rows
            elif call_count == 2:
                mock_r.fetchall.return_value = keyword_rows
            else:
                mock_r.fetchall.return_value = []
            return mock_r

        session.execute = AsyncMock(side_effect=mock_execute)

        results = await hybrid_search("test", 5, session, provider)
        # The overlapping section should be ranked first
        assert results[0].section_number == "OVERLAP"
        # Its score should be higher than single-retriever results
        overlap_score = results[0].score
        for r in results[1:]:
            assert r.score < overlap_score

    async def test_rrf_formula_exact_values(self):
        """Verify RRF formula: 1/(60+rank+1) per retriever."""
        # A doc ranked #1 in both retrievers should get 2 * 1/(60+1) = 2/61
        expected = 2.0 / (RRF_K + 1)

        provider = AsyncMock()
        provider.embed_single.return_value = [0.1] * 1536
        session = AsyncMock()

        semantic_rows = [_make_row(1, "X", "X", None, 0.9)]
        keyword_rows = [_make_row(1, "X", "X", None, 0.8)]

        call_count = 0
        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_r = MagicMock()
            if call_count == 1:
                mock_r.fetchall.return_value = semantic_rows
            elif call_count == 2:
                mock_r.fetchall.return_value = keyword_rows
            else:
                mock_r.fetchall.return_value = []
            return mock_r

        session.execute = AsyncMock(side_effect=mock_execute)

        results = await hybrid_search("test", 5, session, provider)
        assert len(results) == 1
        assert abs(results[0].score - expected) < 1e-10


@pytest.mark.integration
class TestSearchIntegration:
    """Integration tests requiring a running PostgreSQL database.

    These tests are skipped by default. Run with: pytest -m integration
    """

    async def test_semantic_search_returns_relevant(self, db_session):
        """Semantic search should return sections relevant to the query."""
        pytest.skip("Requires running PostgreSQL with seeded data")

    async def test_keyword_search_exact_terms(self, db_session):
        """Keyword search should match exact terms in section content."""
        pytest.skip("Requires running PostgreSQL with seeded data")

    async def test_hybrid_combines_signals(self, db_session):
        """Sections matching both semantically and by keyword should rank higher."""
        pytest.skip("Requires running PostgreSQL with seeded data")

    async def test_graph_boost_promotes_related(self, db_session):
        """Graph boost should surface sections related to top results."""
        pytest.skip("Requires running PostgreSQL with seeded data")

    async def test_recall_at_5(self, db_session):
        """Hybrid search should achieve >80% recall@5 on test queries."""
        pytest.skip("Requires running PostgreSQL with seeded data")
