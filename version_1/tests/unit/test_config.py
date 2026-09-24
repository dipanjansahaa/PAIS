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
