# CrossCures - Pre-Visit Adaptive Questionnaire

## What

An adaptive symptom questionnaire engine for CrossCures Stage 1 (Pre-Visit Intelligence). Given a patient's medical profile, it generates a personalized check-in questionnaire with branching logic -- questions adapt in real time based on the patient's conditions and responses.

**Key capabilities:**
- Generates 4-12 questions per patient based on confirmed conditions (diabetes, hypertension, cardiac, respiratory)
- **Dual-mode generation**: Static (hardcoded question bank with branching) or LLM-powered (cloud via OpenRouter, or local via Ollama/any OpenAI-compatible server)
- Branching logic: follow-up questions trigger conditionally (e.g., pain >= 7 prompts a location detail question)
- **Chain-of-Thought reasoning**: LLM mode shows clinical reasoning for each question selection
- **Dynamic model selection**: Choose from 8 curated free OpenRouter models at runtime
- Supports 4 question types: yes/no, 1-10 scale, multiple choice, free text
- Swappable data sources: mock patients for demo, DuckDB for real OMOP CDM data

## Why

Before a clinic visit, patients need a structured way to report symptoms so physicians arrive prepared. A static questionnaire wastes time on irrelevant questions. This engine tailors the check-in to each patient's condition profile, producing higher-quality pre-visit data in less time.

This MVP validates the core adaptive logic and provides an A/B comparison between static branching and LLM-powered personalization.

## How

### Project Structure

**Architecture Pattern: Layered MVC + Repository**

- **Models Layer** (`models/`): Type-safe schemas and domain enums
- **Services Layer** (`services/`): Business logic for question generation, LLM integration, and voice processing
- **Controllers Layer** (`controllers/`): FastAPI route handlers that orchestrate services
- **Data Layer** (`repositories/`): Abstract provider interface with mock and DuckDB implementations
- **Presentation Layer** (`views/`): Single-page web application with vanilla JS

**Question Generation Strategy** -- The `QuestionnaireGenerator` abstract interface has two implementations:
- `StaticQuestionnaireGenerator` -- hardcoded question bank with deterministic branching logic
- `LLMQuestionnaireGenerator` -- calls an LLM to generate personalized questions with Chain-of-Thought reasoning

**LLM Provider Strategy** -- The `LLMProvider` protocol (`services/llm/provider.py`) has two implementations:
- `CloudLLMProvider` -- OpenRouter cloud API with 8 curated free models
- `LocalLLMProvider` -- Ollama or any OpenAI-compatible local server

Providers are managed by a registry (`services/llm/__init__.py`) with `get_provider("cloud"|"local")`, keeping provider logic fully decoupled from generation logic.

### Setup

This project uses **uv workspaces** with clean package-level imports for modularity. From the repo root:

```bash
# cd  to `crosscures` sub-project folder, i.e. the parent folder of this README

# Install all workspace dependencies (runs from repo root)
uv sync

# Start the API server
uv run uvicorn app:app --host 0.0.0.0 --reload --port 8000
```

### LLM Mode Setup (Optional)

To enable LLM-powered question generation, create a `.env` file in the repo root with your [OpenRouter](https://openrouter.ai/) API key:

```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

The UI will show a **Static | LLM** toggle. When LLM mode is selected, a model dropdown appears with 8 curated free models:

| Model | Why |
|-------|-----|
| Qwen3 Coder 480B (35B active) | Largest active params, best JSON output |
| StepFun Step 3.5 Flash | Health #38 ranking, reasoning model |
| Llama 3.3 70B Instruct | Battle-tested, reliable JSON |
| OpenAI gpt-oss-120b | Strong instruction following |
| NVIDIA Nemotron 3 Super | Good reasoning, 1M context |
| Mistral Small 3.1 24B | Fast and efficient |
| Google Gemma 3 27B | Solid general capability |
| Nous Hermes 3 405B | Very large, great reasoning |

Without an API key, Static mode works normally and the Cloud LLM button is disabled.

### Local LLM Setup (Optional)

To run question generation against a local model (no API key needed, fully offline):

1. **Install Ollama** (or any OpenAI-compatible server):

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or via Homebrew on macOS
brew install ollama
```

2. **Pull a model** -- small models work well for JSON generation:

```bash
ollama pull gemma3:1b      # ~1 GB, fast
ollama pull llama3.2:3b    # ~2 GB, better quality
ollama pull phi4-mini       # ~2.5 GB, good reasoning
```

3. **Start the Ollama server** (if not already running):

```bash
ollama serve
```

By default, Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`. The app auto-detects this.

**Optional `.env` overrides:**

```bash
# Change the local server URL (default: http://localhost:11434/v1)
LOCAL_LLM_BASE_URL=http://localhost:11434/v1

# Change the default local model (default: gemma3:1b)
LOCAL_LLM_MODEL=llama3.2:3b
```

The UI shows a three-way toggle: **Static | Cloud LLM | Local LLM**. When Local LLM is selected, a dropdown lists all models available on your local server.

**Using other OpenAI-compatible servers** (vLLM, llama.cpp, LM Studio, etc.):

Set `LOCAL_LLM_BASE_URL` to point at the server's OpenAI-compatible endpoint. For example:

```bash
# llama.cpp server
LOCAL_LLM_BASE_URL=http://localhost:8080/v1

# vLLM
LOCAL_LLM_BASE_URL=http://localhost:8000/v1

# LM Studio
LOCAL_LLM_BASE_URL=http://localhost:1234/v1
```

### Voice Mode Setup (Cartesia + VoiceAgent)

The questionnaire UI now supports hands-free voice flow:
- Reads each question using Cartesia TTS
- Captures spoken answers from microphone audio
- Transcribes with Cartesia STT
- Auto-submits and advances to the next question
- Forwards transcripts to mounted `voice_agent` websocket session

Add these variables to `.env` (repo root):

```bash
CARTESIA_API_KEY=your-cartesia-key
CARTESIA_VERSION=2026-03-01
CARTESIA_TTS_MODEL=sonic-3
CARTESIA_STT_MODEL=ink-whisper
CARTESIA_VOICE_ID=694f9389-aac1-45b6-b726-9d9369183238

# Required for mounted voice_agent websocket session
ANTHROPIC_API_KEY=your-anthropic-key
```

Voice endpoints exposed by API server:
- `POST /voice/tts`
- `POST /voice/stt`
- `GET /voice/status`
- `GET /voice-agent/status`

### Quick Start (User)

1. Open `http://localhost:8001/index.html` in your browser
2. Select a generator mode: **Static** (deterministic branching), **Cloud LLM** (OpenRouter), or **Local LLM** (Ollama)
3. If Cloud or Local LLM mode, pick a model from the dropdown
4. Select a patient (4 mock patients with different condition profiles)
5. Answer the adaptive questionnaire -- notice branching (Static) or CoT reasoning panel (LLM)
6. View the completed check-in summary

To switch to real patient data from DuckDB:

```bash
curl -X POST "http://localhost:8000/data-source/switch-to-duckdb?db_path=data/ehrshots/patient_data.duckdb"
```

Refresh the UI to see patients loaded from DuckDB.

### Quick Start (Developer)

**API docs**: `http://localhost:8000/docs` (Swagger UI, auto-generated)

**Core API flow:**

```bash
# 1. List patients
curl http://localhost:8000/patients

# 2. Start a check-in session (static mode)
curl -X POST http://localhost:8000/checkin/initialize \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PAT001"}'

# 2b. Start a check-in session (Cloud LLM mode with model selection)
curl -X POST http://localhost:8000/checkin/initialize \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PAT001", "mode": "llm", "model": "meta-llama/llama-3.3-70b-instruct:free"}'

# 2c. Start a check-in session (Local LLM mode)
curl -X POST http://localhost:8000/checkin/initialize \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PAT001", "mode": "local", "model": "gemma3:1b"}'

# 3. Submit a response (use session_id from step 2)
curl -X POST http://localhost:8000/checkin/submit-response \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "response": {"question_id": "base_001", "response_value": 7}}'

# 4. Complete the check-in
curl -X POST http://localhost:8000/checkin/complete \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID"}'
```

**Test the generator directly:**

```python
from services import AdaptiveQuestionnaireGenerator
from models import PatientProfile, PatientCondition

gen = AdaptiveQuestionnaireGenerator()
patient = PatientProfile(
    patient_id="test",
    name="Test Patient",
    conditions=[
        PatientCondition(condition_name="Type 2 Diabetes"),
        PatientCondition(condition_name="Hypertension"),
    ],
)

questions = gen.generate_questionnaire(patient)
for q in questions:
    print(f"[{q.condition_tag}] {q.question_id}: {q.question_text[:60]}")
```

**Run tests:**

```bash
uv run pytest
```
