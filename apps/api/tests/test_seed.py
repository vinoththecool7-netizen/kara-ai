"""Tests to validate tax_sections.yaml data integrity."""
import re
from pathlib import Path

import pytest
import yaml

DATA_FILE = Path(__file__).parent.parent / "src" / "kara_api" / "data" / "tax_sections.yaml"

class TestTaxSectionsData:
    @pytest.fixture(autouse=True)
    def load_data(self):
        with open(DATA_FILE) as f:
            self.data = yaml.safe_load(f)
        self.sections = self.data["sections"]
        self.relationships = self.data.get("relationships", [])

    def test_load_yaml_parses_all_sections(self):
        assert len(self.sections) >= 100

    def test_each_section_has_required_fields(self):
        required = {"section_number", "title", "content", "ltree_path"}
        for section in self.sections:
            missing = required - set(section.keys())
            assert not missing, f"Section {section.get('section_number', '?')} missing: {missing}"

    def test_section_numbers_unique(self):
        numbers = [s["section_number"] for s in self.sections]
        dupes = [n for n in numbers if numbers.count(n) > 1]
        assert not dupes, f"Duplicate section numbers: {set(dupes)}"

    def test_relationships_reference_valid_sections(self):
        valid = {s["section_number"] for s in self.sections}
        for rel in self.relationships:
            assert rel["parent"] in valid, f"Unknown parent: {rel['parent']}"
            assert rel["child"] in valid, f"Unknown child: {rel['child']}"

    def test_ltree_paths_valid_format(self):
        pattern = re.compile(r"^[a-z_][a-z_0-9]*(\.[a-z_][a-z_0-9]*)+$")
        for section in self.sections:
            path = section["ltree_path"]
            assert pattern.match(path), f"Invalid ltree path '{path}' for {section['section_number']}"
