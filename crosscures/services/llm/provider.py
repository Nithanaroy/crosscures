"""LLM Provider Protocol - Strategy interface for LLM backends."""
from typing import Protocol


class LLMProvider(Protocol):
    """Strategy interface for LLM backends (cloud, local, etc.)."""

    @property
    def name(self) -> str:
        """Human-readable label for logging (e.g. 'OpenRouter', 'Ollama')."""
        ...

    @property
    def default_model(self) -> str:
        """Model ID to use when none is specified."""
        ...

    def is_available(self) -> bool:
        """Check whether the provider is configured and reachable."""
        ...

    def get_models(self) -> list[dict]:
        """Return available models as a list of {id, name, note, ...} dicts."""
        ...

    def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """
        Send a chat completion request and return the response text.

        Raises LLMError on failure.
        """
        ...
