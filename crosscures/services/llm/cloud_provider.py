"""Cloud LLM Provider - OpenRouter via OpenAI SDK."""
import os
import logging
from openai import OpenAI

from services.llm.errors import LLMError

logger = logging.getLogger(__name__)

# Curated free models suitable for clinical questionnaire generation.
AVAILABLE_MODELS = [
    {
        "id": "qwen/qwen3-coder-480b-a35b:free",
        "name": "Qwen3 Coder 480B (35B active)",
        "context": 262000,
        "note": "Largest active params, best JSON output",
    },
    {
        "id": "stepfun/step-3.5-flash:free",
        "name": "StepFun Step 3.5 Flash",
        "context": 256000,
        "note": "Health #38 ranking, reasoning model",
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct:free",
        "name": "Llama 3.3 70B Instruct",
        "context": 65536,
        "note": "Battle-tested, reliable JSON",
    },
    {
        "id": "openai/gpt-oss-120b:free",
        "name": "OpenAI gpt-oss-120b",
        "context": 131072,
        "note": "Strong instruction following",
    },
    {
        "id": "nvidia/nemotron-3-super-120b-a12b:free",
        "name": "NVIDIA Nemotron 3 Super",
        "context": 262144,
        "note": "Good reasoning, 1M context",
    },
    {
        "id": "mistralai/mistral-small-3.1-24b-instruct:free",
        "name": "Mistral Small 3.1 24B",
        "context": 128000,
        "note": "Fast and efficient",
    },
    {
        "id": "google/gemma-3-27b-it:free",
        "name": "Google Gemma 3 27B",
        "context": 131072,
        "note": "Solid general capability",
    },
    {
        "id": "nousresearch/hermes-3-llama-3.1-405b:free",
        "name": "Nous Hermes 3 405B",
        "context": 131072,
        "note": "Very large, great reasoning",
    },
]


class CloudLLMProvider:
    """OpenRouter cloud LLM provider."""

    def __init__(self):
        self._client: OpenAI | None = None

    @property
    def name(self) -> str:
        return "OpenRouter"

    @property
    def default_model(self) -> str:
        return os.environ.get("OPENROUTER_MODEL", AVAILABLE_MODELS[0]["id"])

    def is_available(self) -> bool:
        return os.environ.get("OPENROUTER_API_KEY") is not None

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
            raise LLMError("OPENROUTER_API_KEY not set")

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
            logger.exception("OpenRouter API call failed")
            raise LLMError(str(exc)) from exc

    def _get_client(self) -> OpenAI | None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return None
        if self._client is None:
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
        return self._client
