from kara_api.config import Settings, get_settings


def test_default_settings():
    settings = Settings()
    assert "asyncpg" in settings.DATABASE_URL
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DEBUG is False


def test_sync_database_url():
    settings = Settings()
    assert "+asyncpg" not in settings.sync_database_url
    assert "postgresql://" in settings.sync_database_url


def test_get_settings_returns_instance():
    settings = get_settings()
    assert isinstance(settings, Settings)


def test_default_cors_origins():
    settings = Settings()
    assert "http://localhost:3000" in settings.CORS_ORIGINS


def test_llm_base_url_default():
    settings = Settings()
    assert settings.LLM_BASE_URL == ""


def test_llm_max_tokens_default():
    settings = Settings()
    assert settings.LLM_MAX_TOKENS == 4096


def test_llm_temperature_default():
    settings = Settings()
    assert settings.LLM_TEMPERATURE == 0.3
