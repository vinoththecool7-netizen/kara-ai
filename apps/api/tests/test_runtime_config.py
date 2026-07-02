"""Tests for the DB-backed runtime configuration layer."""

from kara_api.config import Settings
from kara_api.runtime_config import (
    WIZARD_KEYS,
    apply_overrides,
    is_env_configured,
    mask_key,
)


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


class TestIsEnvConfigured:
    def test_default_settings_are_unconfigured(self):
        assert is_env_configured(_settings()) is False

    def test_api_key_locks_config_to_env(self):
        assert is_env_configured(_settings(LLM_API_KEY="sk-test")) is True

    def test_ollama_provider_locks_config_to_env(self):
        assert is_env_configured(_settings(LLM_PROVIDER="ollama")) is True

    def test_fake_provider_locks_config_to_env(self):
        assert is_env_configured(_settings(LLM_PROVIDER="fake")) is True


class TestMaskKey:
    def test_empty_key(self):
        assert mask_key("") == ""

    def test_long_key_shows_last_four(self):
        assert mask_key("sk-abcdefghijklmnop") == "••••mnop"

    def test_short_key_fully_masked(self):
        assert mask_key("short") == "••••"


class TestApplyOverrides:
    def test_overlays_wizard_keys(self):
        settings = _settings()
        out = apply_overrides(
            settings, {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "sk-ant-1234"}
        )
        assert out.LLM_PROVIDER == "anthropic"
        assert out.LLM_API_KEY == "sk-ant-1234"
        # untouched fields keep their values
        assert out.SESSION_TTL_DAYS == settings.SESSION_TTL_DAYS

    def test_ignores_non_wizard_keys(self):
        out = apply_overrides(_settings(), {"DATABASE_URL": "postgresql://evil"})
        assert "evil" not in out.DATABASE_URL

    def test_empty_overrides_returns_equivalent_settings(self):
        settings = _settings()
        assert apply_overrides(settings, {}) == settings


def test_wizard_keys_are_valid_settings_fields():
    for key in WIZARD_KEYS:
        assert key in Settings.model_fields
