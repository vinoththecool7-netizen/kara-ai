"""Tests for knowledge-base seeding helper functions."""
import pytest

from kara_api.knowledge.seeding import build_embedding_text, load_sections_data


class TestBuildEmbeddingText:
    def test_includes_all_fields(self):
        section = {
            "section_number": "80C",
            "ltree_path": "income_tax.deductions.s80c",
            "title": "Section 80C",
            "content": "Investment deductions under 80C.",
            "summary": "Tax saving investments.",
            "common_questions": ["What is 80C?", "How much can I save?"],
        }
        result = build_embedding_text(section)
        assert "Section 80C" in result
        assert "Investment deductions under 80C." in result
        assert "Tax saving investments." in result
        assert "What is 80C?" in result
        assert "How much can I save?" in result

    def test_handles_missing_optional_fields(self):
        section = {
            "section_number": "TEST",
            "ltree_path": "income_tax.test",
            "title": "Test Title",
            "content": "Test content here.",
        }
        result = build_embedding_text(section)
        assert result == "Test Title\nTest content here."


class TestLoadSectionsData:
    def test_returns_dict_with_sections(self):
        data = load_sections_data()
        assert isinstance(data, dict)
        assert "sections" in data

    def test_raises_on_missing_sections_key(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("relationships: []\n")
        with pytest.raises(ValueError, match="missing top-level 'sections' key"):
            load_sections_data(bad)

    def test_raises_on_missing_required_fields(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("sections:\n  - section_number: X\n")
        with pytest.raises(ValueError, match="missing required fields"):
            load_sections_data(bad)
