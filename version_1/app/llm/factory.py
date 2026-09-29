"""Factory for configured LLM providers."""

from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.providers.ollama import OllamaProvider


def get_llm_provider() -> LLMProvider:
    """Create the configured LLM provider."""

    provider = settings.llm_provider.strip().lower()

    if provider == "ollama":
        return OllamaProvider(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout,
        )

    raise ValueError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )