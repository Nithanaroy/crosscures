# CrossCures - Pre-Visit Adaptive Questionnaire

## What

An adaptive symptom questionnaire engine for CrossCures Stage 1 (Pre-Visit Intelligence). Given a patient's medical profile, it generates a personalized check-in questionnaire with branching logic -- questions adapt in real time based on the patient's conditions and responses.

**Key capabilities:**
- Generates 4-12 questions per patient based on confirmed conditions (diabetes, hypertension, cardiac, respiratory)
- Branching logic: follow-up questions trigger conditionally (e.g., pain >= 7 prompts a location detail question)
- Supports 4 question types: yes/no, 1-10 scale, multiple choice, free text
- Swappable data sources: mock patients for demo, DuckDB for real OMOP CDM data

## Why

Before a clinic visit, patients need a structured way to report symptoms so physicians arrive prepared. A static questionnaire wastes time on irrelevant questions. This engine tailors the check-in to each patient's condition profile, producing higher-quality pre-visit data in less time.

This MVP validates the core adaptive logic before integrating LLM personalization, the memory layer, and pre-visit brief generation in later stages.

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
│   └── generator.py          # Adaptive question engine
├── controllers/
│   └── checkin.py            # API route handlers
└── repositories/
    ├── base.py               # Abstract data provider interface
    └── providers.py          # Mock + DuckDB implementations
```

Pattern: **MVC + Repository**. Business logic (services) is framework-agnostic and testable without FastAPI. Data access (repositories) is abstracted behind interfaces so mock and DuckDB sources are interchangeable at runtime.

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

### Quick Start (User)

1. Open `http://localhost:8001/index.html` in your browser
2. Select a patient (4 mock patients with different condition profiles)
3. Answer the adaptive questionnaire -- notice branching in action
4. View the completed check-in summary

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

# 2. Start a check-in session
curl -X POST http://localhost:8000/checkin/initialize \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PAT001"}'

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
