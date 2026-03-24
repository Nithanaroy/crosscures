import os
from fastapi import FastAPI
from line import CallRequest
from line.llm_agent import LlmAgent, LlmConfig, end_call
from line.voice_agent_app import AgentEnv, VoiceAgentApp
from voice_agent import env

# Compatibility shim: some FastAPI versions renamed
# `add_websocket_route` -> `add_api_websocket_route`. The
# upstream `line` package may call the old name; provide an
# alias so VoiceAgentApp works across FastAPI versions.
if not hasattr(FastAPI, "add_websocket_route"):
    def _add_websocket_route(self, path, endpoint, *args, **kwargs):
        return self.add_api_websocket_route(path, endpoint, *args, **kwargs)

    FastAPI.add_websocket_route = _add_websocket_route

# ── Pre-feed context ─────────────────────────────────────────────────────────
# Load from a file, env var, or hardcode it here.
def load_context() -> str:
    context_file = env.CONTEXT_FILE
    if os.path.exists(context_file):
        with open(context_file) as f:
            return f.read().strip()
    return os.getenv("AGENT_CONTEXT", "")   # fallback to env var

# ── Who to greet ─────────────────────────────────────────────────────────────
# Use environment variable if set, otherwise fall back to hardcoded defaults
GREET_NAME = os.getenv("GREET_NAME", env.GREET_NAME)

BASE_SYSTEM_PROMPT = """
You are a friendly, conversational voice assistant.
Keep your replies concise — this is a spoken conversation, not a chat.
Use end_call to close the conversation gracefully when the user is done.
"""

# ── Agent factory ─────────────────────────────────────────────────────────────
async def get_agent(env: AgentEnv, call_request: CallRequest):
    context = load_context()

    # Merge base prompt + any pre-fed context
    system_prompt = BASE_SYSTEM_PROMPT
    if context:
        system_prompt += f"\n\n--- Context ---\n{context}"

    return LlmAgent(
        model=os.getenv("MODEL", env.MODEL),
        api_key=os.getenv("ANTHROPIC_API_KEY", env.ANTHROPIC_API_KEY),
        tools=[end_call],
        config=LlmConfig(
            system_prompt=system_prompt,
            introduction=f"Hello {GREET_NAME}! How can I help you today?",
        ),
    )

app = VoiceAgentApp(get_agent=get_agent)

if __name__ == "__main__":
    app.run()
