"""Tests for seed_knowledge_base.py helper functions."""
import sys
from pathlib import Path
import pytest

# Add scripts dir to path so we can import the seed module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from seed_knowledge_base import build_embedding_text, load_yaml, validate_yaml


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
        assert "Test Title" in result
        assert "Test content here." in result
        # Should not crash, just have title and content
        assert result == "Test Title\nTest content here."


class TestLoadYaml:
    def test_load_yaml_returns_dict(self):
        data = load_yaml()
        assert isinstance(data, dict)
        assert "sections" in data


class TestValidateYaml:
    def test_raises_on_missing_sections_key(self):
        with pytest.raises(ValueError, match="missing top-level 'sections' key"):
            validate_yaml({})

    def test_raises_on_missing_required_fields(self):
        data = {"sections": [{"section_number": "X"}]}
        with pytest.raises(ValueError, match="missing required fields"):
            validate_yaml(data)
