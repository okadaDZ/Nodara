from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_NAME = "Nodara API"


class DatabaseSettings(BaseSettings):
    database_url: str = Field(default="sqlite:///./app.db", validation_alias="DATABASE_URL")


class LLMSettings(BaseSettings):
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    vision_model: str = Field(default="gpt-4o-mini", validation_alias="VISION_MODEL")
    transcription_model: str = Field(default="whisper-1", validation_alias="TRANSCRIPTION_MODEL")
    llm_temperature: float = Field(default=0.0, validation_alias="LLM_TEMPERATURE")
    llm_request_timeout_seconds: int = Field(default=120, validation_alias="LLM_REQUEST_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=2, validation_alias="LLM_MAX_RETRIES")
    models_cache_ttl_seconds: int = Field(default=300, validation_alias="MODELS_CACHE_TTL_SECONDS")
    use_mock_ai_fallback: bool = Field(default=True, validation_alias="USE_MOCK_AI_FALLBACK")


class LangfuseSettings(BaseSettings):
    use_langfuse: bool = Field(default=False, validation_alias="USE_LANGFUSE")
    langfuse_public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com", validation_alias="LANGFUSE_BASE_URL"
    )
    langfuse_tracing_environment: str = Field(
        default="development", validation_alias="LANGFUSE_TRACING_ENVIRONMENT"
    )
    langfuse_sample_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, validation_alias="LANGFUSE_SAMPLE_RATE"
    )


class NewsApiSettings(BaseSettings):
    news_api_key: str = Field(default="", validation_alias="NEWS_API_KEY")
    news_api_base_url: str = Field(
        default="https://newsapi.org/v2", validation_alias="NEWS_API_BASE_URL"
    )
    news_api_timeout_seconds: float = Field(
        default=15.0, gt=0, validation_alias="NEWS_API_TIMEOUT_SECONDS"
    )
    news_api_page_size: int = Field(
        default=10, ge=1, le=100, validation_alias="NEWS_API_PAGE_SIZE"
    )


class AppSettings(DatabaseSettings, LLMSettings, LangfuseSettings, NewsApiSettings):
    project_name: str = PROJECT_NAME
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    default_log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    api_auth_token: str = Field(default="", validation_alias="API_AUTH_TOKEN")

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()
