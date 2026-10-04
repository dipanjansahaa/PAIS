"""Unit tests for application configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_defaults() -> None:
    settings = Settings()

    assert settings.app_name == "PAIS"
    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.log_level == "INFO"


def test_settings_load_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "PAIS Test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test_db",
    )
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings()

    assert settings.app_name == "PAIS Test"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.database_url == (
        "postgresql+asyncpg://test:test@localhost:5432/test_db"
    )
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize("app_env", ["invalid", "", "prod"])
def test_settings_reject_invalid_environment(app_env: str) -> None:
    with pytest.raises(ValidationError):
        Settings(app_env=app_env)


def test_settings_reject_invalid_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///pais.db")


@pytest.mark.parametrize("log_level", ["TRACE", "VERBOSE", "INVALID"])
def test_settings_reject_invalid_log_level(log_level: str) -> None:
    with pytest.raises(ValidationError):
        Settings(log_level=log_level)


def test_settings_normalize_case_and_whitespace() -> None:
    settings = Settings(
        app_name="  PAIS Local  ",
        app_env=" DEVELOPMENT ",
        log_level=" warning ",
    )

    assert settings.app_name == "PAIS Local"
    assert settings.app_env == "development"
    assert settings.log_level == "WARNING"


def test_settings_reject_empty_app_name() -> None:
    with pytest.raises(ValidationError):
        Settings(app_name="   ")


def test_embedding_settings() -> None:
    settings = Settings()

    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_device == "cpu"
    assert settings.embedding_batch_size == 32
    assert settings.embedding_normalize is True


def test_llm_settings() -> None:
    """Settings should expose the configured LLM values."""
    settings = Settings(
        llm_provider="ollama",
        llm_model="llama3.2:3b",
        llm_base_url="http://localhost:11434",
        llm_temperature=0.0,
        llm_timeout=60.0,
    )

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "llama3.2:3b"
    assert settings.llm_base_url == "http://localhost:11434"
    assert settings.llm_temperature == 0.0
    assert settings.llm_timeout == 60.0


def test_development_allows_default_security_configuration() -> None:
    """Development configuration may use local development defaults."""

    settings = Settings(
        app_env="development",
        auth_jwt_secret=None,
        database_url="postgresql+asyncpg://pais:pais@localhost:5432/pais",
    )

    assert settings.app_env == "development"


def test_production_requires_jwt_secret() -> None:
    """Production configuration must define a JWT secret."""

    with pytest.raises(ValueError, match="AUTH_JWT_SECRET"):
        Settings(
            app_env="production",
            auth_jwt_secret=None,
            database_url=(
                "postgresql+asyncpg://pais:secure-password@db:5432/pais"
            ),
        )


def test_staging_requires_jwt_secret() -> None:
    """Staging configuration must define a JWT secret."""

    with pytest.raises(ValueError, match="AUTH_JWT_SECRET"):
        Settings(
            app_env="staging",
            auth_jwt_secret="   ",
            database_url=(
                "postgresql+asyncpg://pais:secure-password@db:5432/pais"
            ),
        )


def test_production_rejects_default_database_url() -> None:
    """Production must not use the local development database URL."""

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            app_env="production",
            auth_jwt_secret="integration-test-secret-that-is-long-enough",
            database_url=(
                "postgresql+asyncpg://pais:pais@localhost:5432/pais"
            ),
        )


def test_production_rejects_default_database_credentials() -> None:
    """Production must not use the default pais/pais database credentials."""

    with pytest.raises(ValueError, match="default development database credentials"):
        Settings(
            app_env="production",
            auth_jwt_secret="integration-test-secret-that-is-long-enough",
            database_url=(
                "postgresql+asyncpg://pais:pais@db:5432/pais"
            ),
        )


def test_production_accepts_explicit_secure_configuration() -> None:
    """Production accepts explicitly configured security settings."""

    settings = Settings(
        app_env="production",
        auth_jwt_secret="integration-test-secret-that-is-long-enough",
        database_url=(
            "postgresql+asyncpg://pais:secure-password@db:5432/pais"
        ),
    )

    assert settings.app_env == "production"
    assert settings.auth_jwt_secret == (
        "integration-test-secret-that-is-long-enough"
    )


def test_upload_size_default() -> None:
    """The default upload limit should be 10 MiB."""

    settings = Settings()

    assert settings.max_upload_size_bytes == 10 * 1024 * 1024


def test_upload_size_loads_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The upload limit should be configurable through the environment."""

    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "5242880")

    settings = Settings()

    assert settings.max_upload_size_bytes == 5 * 1024 * 1024