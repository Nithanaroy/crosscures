#!/usr/bin/env bash
set -euo pipefail

# Simple, idempotent installer for local dev tools used by the voice agent.
# Uses ASCII-only log tags to avoid encoding issues on some terminals.

if ! command -v curl >/dev/null 2>&1; then
	echo "[ERROR]: curl not found. Please install curl and re-run this script."
	exit 1
fi

# Install Cartesia CLI if missing
if ! command -v cartesia >/dev/null 2>&1; then
	echo "[INFO]: Installing Cartesia CLI..."
	curl -fsSL https://cartesia.sh | sh
	echo "[INFO]: Cartesia installed. Run 'cartesia auth login' to authenticate."
else
	echo "[INFO]: cartesia already installed, skipping."
fi

# Install uv (Python package manager) if missing
if ! command -v uv >/dev/null 2>&1; then
	echo "[INFO]: Installing uv..."
	curl -LsSf https://astral.sh/uv/install.sh | sh
	echo "[INFO]: uv installed."
else
	echo "[INFO]: uv already installed, skipping."
fi

# Bootstrap your project (safe: do not overwrite existing directory)
proj_dir="voice_agent"
if [ -d "$proj_dir" ]; then
	echo "[WARN]: $proj_dir already exists. Skipping 'uv init'."
else
	echo "[INFO]: Bootstrapping project: $proj_dir"
	uv init "$proj_dir" || { echo "[ERROR]: 'uv init' failed"; exit 1; }
	(cd "$proj_dir" && uv add cartesia-line) || { echo "[ERROR]: 'uv add' failed"; exit 1; }
fi

echo "[DONE]: setup script finished."
