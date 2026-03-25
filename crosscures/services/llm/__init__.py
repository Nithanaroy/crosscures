"""LLM provider registry - Strategy pattern factory."""
import logging
from dotenv import load_dotenv

from models.constants import PROJECT_HOME
from services.llm.errors import LLMError
from services.llm.provider import LLMProvider
from services.llm.cloud_provider import CloudLLMProvider
from services.llm.local_provider import LocalLLMProvider

logger = logging.getLogger(__name__)

# Load .env once at import time (same as old llm_client.py)
try:
    load_dotenv(PROJECT_HOME / ".env")
except Exception:
    logger.warning("Failed to load .env file")

# Singleton provider instances
_cloud = CloudLLMProvider()
_local = LocalLLMProvider()

_PROVIDERS: dict[str, LLMProvider] = {
    "cloud": _cloud,
    "local": _local,
}


def get_provider(mode: str) -> LLMProvider:
    """Return the LLMProvider for the given mode ('cloud' or 'local')."""
    provider = _PROVIDERS.get(mode)
    if provider is None:
        raise LLMError(f"Unknown provider mode: {mode}")
    return provider


__all__ = [
    "LLMError",
    "LLMProvider",
    "CloudLLMProvider",
    "LocalLLMProvider",
    "get_provider",
]
