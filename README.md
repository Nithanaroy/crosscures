# CrossCures — AI Health Companion

An AI-powered health companion platform with three stages:
- **Stage 1 — Pre-Visit Intelligence**: Adaptive symptom check-ins + AI-generated physician briefs
- **Stage 2 — Clinic Companion**: Voice-enabled AI support during medical appointments (Cartesia TTS/STT)  
- **Stage 3 — Therapy Guardian**: Prescription outcome monitoring with physician alerts

## Architecture

```
crosscure/
├── backend/          # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── consent/      # Granular consent management
│   │   ├── events/       # Typed event bus (PostgreSQL outbox)
│   │   ├── ingestion/    # FHIR R4 JSON + PDF health record ingestion
│   │   ├── memory/       # Memory writer (semantic, episodic, prescription)
│   │   ├── agent/        # LLM interface (Claude), context assembly, validator
│   │   ├── stages/       # Pre-visit, Clinic, Therapy Guardian
│   │   └── api/          # FastAPI routes (patient, physician, voice)
│   ├── main.py
│   └── pyproject.toml
└── frontend/         # Next.js 14 (TypeScript)
    ├── app/
    │   ├── login/         # Auth pages
    │   ├── register/      # 3-step registration with consent
    │   ├── patient/       # Patient portal (home, checkin, clinic, records, medications, settings)
    │   └── physician/     # Physician dashboard (dashboard, patients, briefs, alerts)
    ├── lib/
    │   ├── api.ts         # Axios API client
    │   ├── cartesia.ts    # Cartesia voice integration (STT + TTS)
    │   └── store.ts       # Zustand auth store
    └── components/        # Shared layout components
```

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m app.seed   # Seeds demo accounts
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

App available at: http://localhost:3000

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Patient | patient@demo.com | demo1234 |
| Physician | physician@demo.com | demo1234 |

## Key Features

### Voice-Enabled Check-in (Cartesia)
- Click "Voice input" on any free-text question to speak your answer
- Powered by Cartesia **ink-whisper** STT model
- Agent responses are read aloud via Cartesia **sonic-3** TTS

### Clinic Companion (Stage 2)
- Voice input for all messages using Cartesia
- Claude claude-sonnet-4-20250514 provides responses grounded in patient records
- Real-time TTS readback with toggle

### Pre-Visit Briefs (Stage 1)
- Generated from last 14 days of symptom logs + wearable data + health records
- Structured 6-section format for physicians
- Requires explicit patient consent before generation

### Therapy Guardian (Stage 3)
- Outcome criteria evaluated on each therapy check-in
- Red-flag side effects trigger immediate severe alert
- Physician acknowledgment required for severe alerts

## API Endpoints

### Patient Routes (`/v1/patient/`)
- `POST /records/upload` — FHIR JSON or PDF upload
- `GET /checkin/today` — Adaptive question set
- `POST /checkin/response` — Submit responses (triggers deviation check if prescription linked)
- `POST /clinic/session/start` — Start Clinic Companion session
- `POST /clinic/session/{id}/turn` — Send message to agent
- `POST /appointments/{id}/generate-brief` — Generate pre-visit brief

### Physician Routes (`/v1/physician/`)
- `GET /dashboard` — Unread briefs and unacknowledged alerts
- `GET /briefs/{id}` — Full brief with all 6 sections
- `POST /briefs/{id}/acknowledge` — Mark brief as reviewed
- `POST /alerts/{id}/acknowledge` — Acknowledge therapy alert

### Voice Routes (`/v1/voice/`)
- `POST /transcribe` — Cartesia ink-whisper STT
- `POST /synthesize` — Cartesia sonic-3 TTS

## Security & Compliance Notes (MVP)

- All LLM calls require `ConsentAction.LLM_INFERENCE` consent
- Health record storage requires `ConsentAction.HEALTH_RECORD_STORAGE`
- Physician brief sharing requires `ConsentAction.PHYSICIAN_BRIEF_SHARING`
- All API actions are logged to an append-only audit log
- Consent is checked before every sensitive operation
- Response validator catches dosage instructions and diagnostic conclusions

## Environment Variables

### Backend (`.env`)
```
ANTHROPIC_API_KEY=sk-ant-...
CARTESIA_API_KEY=sk_car_...
CARTESIA_VERSION=2026-03-01
CARTESIA_TTS_MODEL=sonic-3
CARTESIA_STT_MODEL=ink-whisper
CARTESIA_VOICE_ID=694f9389-aac1-45b6-b726-9d9369183238
```

### Frontend (`.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CARTESIA_API_KEY=sk_car_...
NEXT_PUBLIC_CARTESIA_VOICE_ID=694f9389-aac1-45b6-b726-9d9369183238
```
