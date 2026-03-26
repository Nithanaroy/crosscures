"""
Gemini LLM Provider - Google Gemini via OpenAI-compatible SDK.

Read https://ai.google.dev/gemini-api/docs/openai for their latest documentation

"""

import os
import logging
from openai import OpenAI

from services.llm.errors import LLMError

logger = logging.getLogger(__name__)

AVAILABLE_MODELS = [
    {
        "id": "gemini-2.5-pro-preview-05-06",
        "name": "Gemini 2.5 Pro Preview",
        "context": 1048576,
        "note": "Most capable, best reasoning",
    },
    {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "context": 1048576,
        "note": "Fast, multimodal, 1M context",
    },
    {
        "id": "gemini-2.0-flash-lite",
        "name": "Gemini 2.0 Flash Lite",
        "context": 1048576,
        "note": "Fastest, lowest cost",
    },
    {
        "id": "gemini-1.5-pro",
        "name": "Gemini 1.5 Pro",
        "context": 2097152,
        "note": "2M context window",
    },
    {
        "id": "gemini-1.5-flash",
        "name": "Gemini 1.5 Flash",
        "context": 1048576,
        "note": "Balanced speed and quality",
    },
]

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiLLMProvider:
    """Google Gemini cloud LLM provider (OpenAI-compatible endpoint)."""

    def __init__(self):
        self._client: OpenAI | None = None

    @property
    def name(self) -> str:
        return "Gemini"

    @property
    def default_model(self) -> str:
        return os.environ.get("GEMINI_MODEL", AVAILABLE_MODELS[1]["id"])

    def is_available(self) -> bool:
        return os.environ.get("GEMINI_API_KEY") is not None

    def get_models(self) -> list[dict]:
        return list(AVAILABLE_MODELS)

    def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:
        client = self._get_client()
        if client is None:
            raise LLMError("GEMINI_API_KEY not set")

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
            logger.exception("Gemini API call failed")
            raise LLMError(str(exc)) from exc

    def _get_client(self) -> OpenAI | None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        if self._client is None:
            self._client = OpenAI(
                base_url=_GEMINI_BASE_URL,
                api_key=api_key,
            )
        return self._client
    

if __name__ == "__main__":
    """Simple test of Gemini provider"""
    from dotenv import load_dotenv
    from models.constants import PROJECT_HOME
    
    load_dotenv(PROJECT_HOME / ".env")
    provider = GeminiLLMProvider()
    
    if not provider.is_available():
        print("Gemini API key not set, skipping test")
    else:
        print("Available models:")
        for m in provider.get_models():
            print(f"- {m['name']} (id: {m['id']}, note: {m['note']})")
        
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ]
        response = provider.chat_completion(test_messages)
        print("Response:", response)
