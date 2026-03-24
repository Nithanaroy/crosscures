import os
from pathlib import Path
from fastapi import FastAPI
from dotenv import load_dotenv

from line import CallRequest
from line.llm_agent import LlmAgent, LlmConfig, end_call
from line.voice_agent_app import AgentEnv, VoiceAgentApp

# ── Load .env explicitly ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── Compatibility shim ────────────────────────────────────────────────────────
if not hasattr(FastAPI, "add_websocket_route"):
    def _add_websocket_route(self, path, endpoint, *args, **kwargs):
        return self.add_api_websocket_route(path, endpoint, *args, **kwargs)

    FastAPI.add_websocket_route = _add_websocket_route

# ── Pre-feed context ─────────────────────────────────────────────────────────
def load_context() -> str:
    context_file = os.getenv("CONTEXT_FILE", "context.txt")
    context_path = BASE_DIR / context_file

    if context_path.exists():
        return context_path.read_text().strip()

    return os.getenv("AGENT_CONTEXT", "")

# ── Config from .env ─────────────────────────────────────────────────────────
GREET_NAME = os.getenv("GREET_NAME", "Sarah")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4-5-20251001")
API_KEY = os.getenv("ANTHROPIC_API_KEY")

BASE_SYSTEM_PROMPT = """
You are a friendly, conversational voice assistant.
Keep your replies concise — this is a spoken conversation, not a chat.
Use end_call to close the conversation gracefully when the user is done.
"""

# ── Agent factory ─────────────────────────────────────────────────────────────
async def get_agent(env: AgentEnv, call_request: CallRequest):
    if not API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")

    context = load_context()

    system_prompt = BASE_SYSTEM_PROMPT
    if context:
        system_prompt += f"\n\n--- Context ---\n{context}"

    return LlmAgent(
        model=MODEL,
        api_key=API_KEY,
        tools=[end_call],
        config=LlmConfig(
            system_prompt=system_prompt,
            introduction=f"Hello {GREET_NAME}! How can I help you today?",
        ),
    )

# ── App ──────────────────────────────────────────────────────────────────────
app = VoiceAgentApp(get_agent=get_agent)

if __name__ == "__main__":
    app.run()