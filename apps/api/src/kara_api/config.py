from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    DATABASE_URL: str = "postgresql+asyncpg://kara:kara@localhost:5432/kara"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    LLM_PROVIDER: str = "openai"
    LLM_BASE_URL: str = ""
    # Comma-separated fallback models, used only with OpenRouter: when the
    # primary model's pool is congested or rate-limited, OpenRouter reroutes
    # to these in order instead of holding the request open.
    LLM_FALLBACK_MODELS: str = ""
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    # Host-header allowlist: blocks DNS-rebinding access to the
    # unauthenticated API. "api" is the compose-internal hostname the web
    # proxy uses; "test"/"testserver" are IANA-reserved names (RFC 6761/2606)
    # that cannot be publicly registered, kept so test clients work.
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "api", "test", "testserver"]
    # Honour X-Forwarded-For for rate limiting only when a trusted reverse
    # proxy sits in front of the API (the header is client-spoofable).
    TRUST_PROXY_HEADERS: bool = False
    DEBUG: bool = False
    # Sessions older than this (by last update) are deleted daily; 0 disables.
    SESSION_TTL_DAYS: int = 30
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CHAT_PER_MINUTE: int = 20
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 10
    RATE_LIMIT_COMPUTE_PER_MINUTE: int = 60
    API_V1_PREFIX: str = "/api/v1"
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
