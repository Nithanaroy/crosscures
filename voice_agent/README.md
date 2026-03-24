USAGE: voice_agent
==================

Prerequisites
- curl
- bash (macOS builtin)
- `uv` (the Astral/uv tool) or a Python virtualenv with Python 3.10+

Quick setup
-----------
Run the repository bootstrap script. The script is idempotent and safe to re-run:

```bash
bash voice_agent/setup.sh
```

Notes:
- If `cartesia` is not installed the script will attempt to install it and will prompt you to run `cartesia auth login` to authenticate.
- If `uv` is not installed the script will attempt to install it.
- The script will not overwrite an existing `voice_agent` directory.

Running the voice agent (local)
-------------------------------
Activate your virtual environment (if you have one), then run:

```bash
source .venv/bin/activate
uv run python voice_agent/main.py
# Or: python voice_agent/main.py
```

Troubleshooting
---------------
- If `bash voice_agent/setup.sh` fails because a required tool is missing, install the tool (for example `brew install curl`) and re-run the script.
- Check permissions if the installer cannot write to your PATH; you may need to follow the installer output to add the tool to your shell profile.

Using a .env file
-----------------
You can create a `.env` file at the repository root to provide development values. The project will load `.env` automatically and will not overwrite existing environment variables.

Example `.env`:

```
GREET_NAME="Alex"
ANTHROPIC_API_KEY=sk-...
MODEL=anthropic/claude-haiku-4-5-20251001
CONTEXT_FILE=voice_agent/context.txt
```

Create the file quickly from the shell:

```bash
echo 'GREET_NAME="Alex"' > .env
echo 'ANTHROPIC_API_KEY=sk-...' >> .env
```

For Claude, get API key from https://platform.claude.com/settings/keys

Security: do NOT commit secrets to version control. Keep API keys out of the repo for production usage.

Further help
------------
Open an issue or ask for clarification if commands here don't match your environment.

[DONE]
