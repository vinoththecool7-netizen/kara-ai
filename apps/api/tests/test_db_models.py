"""Unit tests for SQLAlchemy models — metadata only, no database needed."""

from kara_api.db.models import Base, MessageRole, RelationshipType


def test_base_has_all_tables():
    expected = {
        "tax_sections",
        "section_relationships",
        "sessions",
        "messages",
        "runtime_settings",
    }
    assert set(Base.metadata.tables.keys()) == expected


def test_tax_sections_columns():
    table = Base.metadata.tables["tax_sections"]
    expected_columns = {
        "id",
        "section_number",
        "ltree_path",
        "title",
        "content",
        "summary",
        "embedding",
        "search_vector",
        "metadata_json",
        "created_at",
        "updated_at",
    }
    assert expected_columns.issubset(set(table.columns.keys()))


def test_session_has_uuid_pk():
    table = Base.metadata.tables["sessions"]
    pk_cols = [col for col in table.primary_key.columns]
    assert len(pk_cols) == 1
    col = pk_cols[0]
    assert col.name == "id"
    # UUID type from SQLAlchemy
    assert "uuid" in str(col.type).lower() or "Uuid" in type(col.type).__name__


def test_message_role_enum_values():
    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.TOOL.value == "tool"
    assert len(MessageRole) == 3


def test_relationship_type_enum_values():
    assert RelationshipType.OVERRIDES.value == "overrides"
    assert RelationshipType.SUPPLEMENTS.value == "supplements"
    assert RelationshipType.REQUIRES.value == "requires"
    assert len(RelationshipType) == 3


def test_section_relationship_unique_constraint():
    table = Base.metadata.tables["section_relationships"]
    constraint_names = [c.name for c in table.constraints if c.name]
    assert "uq_section_relationship" in constraint_names


def test_runtime_setting_model_mapping():
    from kara_api.db.models import RuntimeSetting

    assert RuntimeSetting.__tablename__ == "runtime_settings"
    setting = RuntimeSetting(key="LLM_PROVIDER", value="openai")
    assert setting.key == "LLM_PROVIDER"
    assert setting.value == "openai"
