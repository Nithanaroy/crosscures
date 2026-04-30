"""Eval pipeline configuration."""
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DUCKDB_PATH = DATA_DIR / "medalign" / "medalign.duckdb"
EXCEL_PATH = DATA_DIR / "Data sheet Xcures.xlsx"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


@dataclass
class LLMConfig:
    """LLM provider config. Supports OpenAI API and Ollama (OpenAI-compatible)."""

    provider: str = "ollama"  # "openai" or "ollama"
    model: str = "llama3"
    base_url: str = "http://localhost:11434/v1"
    api_key: str = ""
    max_tokens: int = 2048
    temperature: float = 0.3

    # Normalizer can use a separate, more powerful model + provider
    normalizer_provider: str = ""  # defaults to self.provider if empty
    normalizer_model: str = ""     # defaults to self.model if empty
    normalizer_base_url: str = ""  # defaults to self.base_url if empty
    normalizer_api_key: str = ""   # defaults to self.api_key if empty

    def __post_init__(self):
        if self.provider == "openai":
            self.base_url = self.base_url or "https://api.openai.com/v1"
            self.api_key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
            if not self.model:
                self.model = "gpt-4o"
        elif self.provider == "ollama":
            self.api_key = self.api_key or "ollama"

        # Normalizer defaults: inherit from generator if not set
        if not self.normalizer_provider:
            self.normalizer_provider = self.provider
        if not self.normalizer_model:
            self.normalizer_model = self.model
        if not self.normalizer_base_url:
            if self.normalizer_provider == "openai":
                self.normalizer_base_url = "https://api.openai.com/v1"
            elif self.normalizer_provider == "ollama":
                self.normalizer_base_url = "http://localhost:11434/v1"
            else:
                self.normalizer_base_url = self.base_url
        if not self.normalizer_api_key:
            if self.normalizer_provider == "openai":
                self.normalizer_api_key = os.environ.get("OPENAI_API_KEY", "")
            elif self.normalizer_provider == "ollama":
                self.normalizer_api_key = "ollama"
            else:
                self.normalizer_api_key = self.api_key


DEFAULT_CONFIG = LLMConfig()
