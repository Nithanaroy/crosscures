"""Environment defaults and simple .env loader for local development.

DO NOT commit secrets here for production. These are convenient
defaults used when corresponding environment variables are not set.
This module will attempt to load a top-level `.env` file and then
expose commonly used defaults as module-level names.
"""

import os
from pathlib import Path


def _load_dotenv(dotenv_path: str | Path = ".env") -> None:
    p = Path(dotenv_path)
    if not p.exists():
        return
    try:
        with p.open() as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                # Do not overwrite existing environment variables
                os.environ.setdefault(key, val)
    except Exception:
        # If reading fails, avoid crashing import — env vars can still be provided externally
        return


# Load .env from repository root (if present)
_load_dotenv()


# Exposed defaults (fall back to environment values when present)
GREET_NAME = os.getenv("GREET_NAME", "there")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4-5-20251001")
CONTEXT_FILE = os.getenv("CONTEXT_FILE", "context.txt")
