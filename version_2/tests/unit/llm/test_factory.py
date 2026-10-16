"""Tests for the LLM provider factory."""

import pytest

from app.core.config import settings
from app.llm.factory import get_llm_provider
from app.llm.providers.ollama import OllamaProvider


def test_get_llm_provider_returns_ollama_provider(monkeypatch):
    """Factory should return the configured Ollama provider."""

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(
        settings,
        "llm_base_url",
        "http://localhost:11434",
    )
    monkeypatch.setattr(settings, "llm_timeout", 60.0)

    provider = get_llm_provider()

    assert isinstance(provider, OllamaProvider)


def test_get_llm_provider_rejects_unsupported_provider(monkeypatch):
    """Factory should reject unsupported provider names."""

    monkeypatch.setattr(settings, "llm_provider", "unsupported")

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider()