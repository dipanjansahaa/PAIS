"""Application configuration and environment loading.""" 

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(
        default="PAIS",
        description="Application display name.",
    )
    app_env: str = Field(
        default="development",
        description="Runtime environment.",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug behavior.",
    )
    database_url: str = Field(
        default="postgresql+asyncpg://pais:pais@localhost:5432/pais",
        description="Async SQLAlchemy database URL.",
    )
    log_level: str = Field(
        default="INFO",
        description="Application logging level.",
    )

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("APP_NAME must not be empty.")
        return value

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = {"development", "test", "staging", "production"}
        if value not in allowed:
            raise ValueError(
                f"APP_ENV must be one of: {', '.join(sorted(allowed))}."
            )
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL must not be empty.")

        supported_schemes = (
            "postgresql://",
            "postgresql+asyncpg://",
        )
        if not value.startswith(supported_schemes):
            raise ValueError(
                "DATABASE_URL must use PostgreSQL with either "
                "'postgresql://' or 'postgresql+asyncpg://'."
            )
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        value = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value not in allowed:
            raise ValueError(
                f"LOG_LEVEL must be one of: {', '.join(sorted(allowed))}."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()


settings = get_settings()
