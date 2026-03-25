"""
OpenRouter LLM Client - Thin wrapper around OpenAI SDK for OpenRouter API.
"""
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

from models.constants import PROJECT_HOME

logger = logging.getLogger(__name__)

try:
    env_file = PROJECT_HOME / ".env"
    load_dotenv(env_file)
except Exception:
    logger.warning("Failed to load .env file")

_client: OpenAI | None = None

# Curated free models suitable for clinical questionnaire generation.
# Ordered by recommendation strength.
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


def get_client() -> OpenAI | None:
    """Get or create singleton OpenAI client configured for OpenRouter."""
    global _client
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    return _client


def get_default_model() -> str:
    return os.environ.get(
        "OPENROUTER_MODEL",
        AVAILABLE_MODELS[0]["id"],
    )


def is_available() -> bool:
    """Check if the LLM client is configured and available."""
    return os.environ.get("OPENROUTER_API_KEY") is not None


def chat_completion(
    messages: list[dict],
    json_mode: bool = False,
    model: str | None = None,
) -> str | None:
    """
    Send a chat completion request to OpenRouter.
    Returns the response content string, or None on failure.
    """
    client = get_client()
    if client is None:
        logger.warning("OPENROUTER_API_KEY not set, LLM unavailable")
        return None

    kwargs: dict = {
        "model": model or get_default_model(),
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


class LLMError(Exception):
    """Raised when an LLM API call fails."""


def get_available_models() -> list[dict]:
    """Return the curated list of available models."""
    return AVAILABLE_MODELS
