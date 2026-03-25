"""Local LLM Provider - Ollama or any OpenAI-compatible local server."""
import os
import logging
from openai import OpenAI

from services.llm.errors import LLMError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434/v1"


class LocalLLMProvider:
    """Local LLM provider (Ollama, llama.cpp server, vLLM, etc.)."""

    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or os.environ.get(
            "LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL
        )
        self._client: OpenAI | None = None

    @property
    def name(self) -> str:
        return "Local LLM"

    @property
    def default_model(self) -> str:
        return os.environ.get("LOCAL_LLM_MODEL", "gemma3:1b")

    def is_available(self) -> bool:
        try:
            self._get_client().models.list()
            return True
        except Exception:
            return False

    def get_models(self) -> list[dict]:
        try:
            response = self._get_client().models.list()
            return [
                {"id": m.id, "name": m.id, "note": "Local model"}
                for m in response.data
            ]
        except Exception:
            logger.warning("Failed to list local models")
            return []

    def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:
        client = self._get_client()

        kwargs: dict = {
            "model": model or self.default_model,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as exc:
            logger.exception("Local LLM API call failed")
            raise LLMError(str(exc)) from exc

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=self._base_url,
                api_key="ollama",  # Ignored by Ollama but required by SDK
            )
        return self._client
