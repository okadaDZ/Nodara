import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./app.db"

    # AI Configuration (OpenAI-compatible)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    VISION_MODEL: str = "gpt-4o-mini"
    TRANSCRIPTION_MODEL: str = "whisper-1"

    # Mock provider fallback when API keys are absent
    USE_MOCK_AI_FALLBACK: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
