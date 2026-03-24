# CrossCures - Pre-Visit Adaptive Questionnaire

## What

An adaptive symptom questionnaire engine for CrossCures Stage 1 (Pre-Visit Intelligence). Given a patient's medical profile, it generates a personalized check-in questionnaire with branching logic -- questions adapt in real time based on the patient's conditions and responses.

**Key capabilities:**
- Generates 4-12 questions per patient based on confirmed conditions (diabetes, hypertension, cardiac, respiratory)
- **Dual-mode generation**: Static (hardcoded question bank with branching) or LLM-powered (personalized via OpenRouter)
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

```
crosscures/
├── app.py                   # FastAPI entry point
├── pyproject.toml            # uv project config
├── views/
│   └── index.html            # Web UI
├── models/
│   └── schemas.py            # Pydantic data models
├── services/
│   ├── generator.py          # QuestionnaireGenerator interface + implementations
│   └── llm_client.py         # OpenRouter LLM client wrapper
├── controllers/
│   └── checkin.py            # API route handlers
└── repositories/
    ├── base.py               # Abstract data provider interface
    └── providers.py          # Mock + DuckDB implementations
```

Pattern: **MVC + Repository**. The `QuestionnaireGenerator` abstract interface has two implementations:
- `StaticQuestionnaireGenerator` -- hardcoded question bank with deterministic branching logic
- `LLMQuestionnaireGenerator` -- calls OpenRouter to generate personalized questions with CoT reasoning

### Setup

This project uses **uv workspaces**. From the repo root:

```bash
cd /Users/nipasuma/Projects/crosscures

# Install all workspace dependencies (runs from repo root)
uv sync

# Start the API server
uv run --package crosscures uvicorn crosscures.app:app --reload --port 8000

# In a separate terminal, serve the web UI
python -m http.server 8001 -d crosscures/views
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

Without an API key, Static mode works normally and the LLM button is disabled.

### Quick Start (User)

1. Open `http://localhost:8001/index.html` in your browser
2. Select a generator mode: **Static** (deterministic branching) or **LLM** (AI-powered)
3. If LLM mode, pick a model from the dropdown
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

# 2b. Start a check-in session (LLM mode with model selection)
curl -X POST http://localhost:8000/checkin/initialize \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PAT001", "mode": "llm", "model": "meta-llama/llama-3.3-70b-instruct:free"}'

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
from crosscures.services import AdaptiveQuestionnaireGenerator
from crosscures.models import PatientProfile, PatientCondition

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
