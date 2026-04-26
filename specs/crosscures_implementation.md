**CrossCures — End-to-End Implementation Plan**

**Core principles**

- Patient data sovereignty: all raw health records, audio, and biometric streams are encrypted per-patient before leaving the device. The cloud never holds plaintext PII outside of ephemeral LLM inference calls, which are zero-retention by contract.
- HIPAA compliance at every boundary: every data store, API call, and third-party integration must be covered by a signed BAA. Encryption at rest (AES-256) and in transit (TLS 1.3) is non-negotiable, not a feature.
- Memory is the source of truth: the LLM never fabricates patient history. Every claim in an agent response must be traceable to a source record in patient memory. Hallucination is a patient safety risk.
- Consent gates everything: no data ingestion, wearable sync, ambient session, or physician communication may proceed without a valid, timestamped consent record for that specific action category. Consent is revocable at any time and revocation is synchronous.
- Stage isolation: Stages 1 (Pre-Visit Intelligence), 2 (Clinic Companion), and 3 (Therapy Guardian) are distinct execution modes with separate triggers, context scopes, output schemas, and delivery targets. A stage 2 session cannot access stage 3 prescription data unless the agent explicitly retrieves it through the memory layer.
- Event-driven state: every health data change, wearable reading, symptom log submission, and physician communication emits a typed, versioned event onto the internal event bus. The agent state is a function of the event log, not mutable in-place.
- Physician interface is output-only in MVP: the agent writes to the physician side (brief, alerts, summaries). It does not read physician notes or orders in real time without an active SMART on FHIR integration.
- Every LLM call is auditable: prompt, completion, model version, token counts, and latency are stored in the audit log for every inference call. This is required for clinical accountability and model iteration.
- Strong typing throughout: all events, memory records, agent inputs, and API payloads use Pydantic v2 models. No untyped dicts cross a module boundary.
- Fail safe, not fail open: if the agent cannot retrieve memory, cannot confirm consent, or cannot reach the LLM, it degrades gracefully and informs the patient — it never guesses or fabricates.

---

**Scope of MVP**

- Core: patient auth, consent system, health record ingestion (FHIR JSON + PDF), event bus, memory layer, agent core
- Data: Apple HealthKit integration (read), manual FHIR record upload, PDF clinical note extraction
- Stage 1: daily adaptive symptom check-in, pre-visit brief generation (72h window), brief delivery via secure email
- Stage 2: in-app clinic session (patient-initiated), on-device STT, context injection from memory, structured session summary export
- Stage 3: prescription monitoring via check-in, outcome deviation detection, physician alert via secure email
- Physician interface: pre-visit brief viewer (web), alert inbox (web), no real-time EHR write-back in MVP
- Mobile: iOS only in MVP (React Native with native HealthKit module), Android deferred
- LLM: Claude claude-sonnet-4-20250514 via Anthropic API (zero-retention inference agreement required before launch)
- Backend: FastAPI, PostgreSQL, S3-compatible object store, Redis for session state

---

**System architecture overview**

- Three logical planes:
  - **Patient plane**: mobile app (iOS), on-device memory cache, HealthKit bridge, on-device STT
  - **Agent plane**: backend agent core (FastAPI), memory store, LLM proxy, event bus
  - **Physician plane**: web dashboard (Next.js), brief/alert delivery service, EHR integration adapter (post-MVP)
- All cross-plane communication goes through the agent plane API. The patient plane and physician plane never communicate directly
- The agent plane is stateless per request: all session state is held in Redis (ephemeral) and the memory store (persistent). No in-process state survives a server restart
- Data flow: health events from patient plane → event bus → memory writer → memory store → agent retrieval → LLM → structured output → delivery service → physician plane

---

**Event bus (crosscures/events/)**

- All internal state changes are modeled as typed events. No direct DB mutations from application code — every write is mediated by an event.
- Base event model:
  - `EventBase` (Pydantic model):
    - `event_id: str` (UUID v7, monotonically increasing)
    - `event_type: EventType` (enum, registry of all event types)
    - `patient_id: str` (required, foreign key to patient record)
    - `occurred_at: datetime` (ISO 8601, required)
    - `emitted_at: datetime` (server timestamp, set by bus on receipt)
    - `source: EventSource` (`"mobile"`, `"wearable"`, `"ehr"`, `"agent"`, `"physician"`)
    - `schema_version: str` (semver, for forward compatibility)
    - `payload: dict` (typed by subclass)
    - `idempotency_key: str | None` (optional, for deduplication on retry)
- Event types (EventType enum):
  - `HEALTH_RECORD_INGESTED` — new FHIR resource or PDF document added
  - `WEARABLE_SYNC_COMPLETED` — batch of HealthKit samples received
  - `SYMPTOM_CHECKIN_SUBMITTED` — patient completed a check-in questionnaire
  - `CLINIC_SESSION_STARTED` — patient opened a stage 2 session
  - `CLINIC_SESSION_ENDED` — stage 2 session completed and summarized
  - `PRESCRIPTION_RECORDED` — agent extracted and confirmed a new prescription from records
  - `THERAPY_CHECKIN_SUBMITTED` — patient submitted a post-therapy check-in
  - `OUTCOME_DEVIATION_DETECTED` — outcome deviation threshold breached
  - `BRIEF_GENERATED` — pre-visit brief created and queued for delivery
  - `ALERT_GENERATED` — physician alert created
  - `CONSENT_GRANTED` — patient granted a consent action
  - `CONSENT_REVOKED` — patient revoked a consent action
- Event bus implementation:
  - MVP: PostgreSQL-backed transactional outbox (events table, worker polling). No external message broker required.
  - Consumers are registered handler functions per EventType. The bus calls all handlers synchronously within a DB transaction in MVP; async fanout is post-MVP.
  - Deduplication: if `idempotency_key` is set and matches an existing event for the same `patient_id` and `event_type` within 24h, the event is dropped silently.
  - Event log is immutable: no updates or deletes. Events are the audit trail.
- `EventBus` API:
  - `emit(event: EventBase) -> str` — validate, persist, and dispatch. Returns `event_id`.
  - `subscribe(event_type: EventType, handler: Callable[[EventBase], None]) -> None` — register a consumer.
  - `replay(patient_id: str, since: datetime, event_types: list[EventType] | None = None) -> list[EventBase]` — ordered replay for memory rebuilding.

---

**Consent system (crosscures/consent/)**

- Philosophy: consent is granular, timestamped, and versioned. Every data action category requires its own consent record. Consent version mismatches block the action.
- `ConsentRecord` (Pydantic model):
  - `consent_id: str` (UUID)
  - `patient_id: str`
  - `action: ConsentAction` (enum)
  - `granted: bool`
  - `granted_at: datetime | None`
  - `revoked_at: datetime | None`
  - `consent_version: str` (semver of the consent text the patient saw)
  - `device_fingerprint: str` (for non-repudiation)
- ConsentAction enum:
  - `HEALTH_RECORD_STORAGE` — store and process uploaded health records
  - `WEARABLE_SYNC` — read and store Apple HealthKit data
  - `AMBIENT_LISTENING` — record and transcribe audio during a clinic session
  - `PHYSICIAN_BRIEF_SHARING` — send pre-visit brief to the linked physician
  - `PHYSICIAN_ALERT_SHARING` — send therapy deviation alerts to the linked physician
  - `LLM_INFERENCE` — send de-identified patient context to LLM for inference
  - `RESEARCH_DATA_USE` — use anonymized data for model improvement (optional, default off)
- `ConsentStore` API:
  - `grant(patient_id: str, action: ConsentAction, consent_version: str, device_fingerprint: str) -> ConsentRecord`
  - `revoke(patient_id: str, action: ConsentAction) -> ConsentRecord`
  - `check(patient_id: str, action: ConsentAction) -> bool` — returns True only if a current, unrevoked record exists at or above the current consent version
  - `require(patient_id: str, action: ConsentAction) -> None` — raises `ConsentError` if `check()` returns False. Used as a guard at every sensitive call site.
  - `get_all(patient_id: str) -> list[ConsentRecord]`
- Errors: `ConsentError` — raised when `require()` fails. Contains `action`, `patient_id`, and `reason` (`"not_granted"` or `"version_mismatch"`).
- MVP simplification: consent text versions are hard-coded constants. Version management UI is post-MVP.

---

**Health record ingestion (crosscures/ingestion/)**

- Philosophy: the patient's clinical history is the foundation of everything. Ingestion must be conservative: ambiguous data is flagged, not discarded or silently mutated.
- Supported input formats in MVP:
  - FHIR R4 JSON bundles (patient uploads from Apple Health Records, CommonHealth)
  - PDF clinical notes (OCR + structured extraction)
- Ingestion pipeline:
  - `IngestRequest` (Pydantic model):
    - `patient_id: str`
    - `source_format: Literal["fhir_r4", "pdf"]`
    - `raw_bytes: bytes`
    - `source_name: str` (e.g., `"Mayo Clinic Patient Portal"`, `"Uploaded PDF"`)
    - `upload_id: str` (idempotency key)
  - `IngestResult` (Pydantic model):
    - `upload_id: str`
    - `records_extracted: int`
    - `records_failed: int`
    - `warnings: list[str]`
    - `extracted_resources: list[FHIRResource]`

- **FHIR R4 parser** (`crosscures/ingestion/fhir.py`)
  - Accepts FHIR R4 Bundle or individual resource JSON
  - Supported resource types in MVP: `Patient`, `Condition`, `MedicationRequest`, `MedicationStatement`, `Observation`, `DiagnosticReport`, `AllergyIntolerance`, `Procedure`, `Encounter`, `DocumentReference`
  - Unsupported resource types are logged and skipped — never rejected silently without a warning
  - `FHIRResource` (Pydantic model):
    - `resource_id: str` (FHIR `id` field)
    - `resource_type: str`
    - `patient_id: str`
    - `occurred_at: datetime | None` (extracted from `effectiveDateTime`, `recordedDate`, `authoredOn`, etc.)
    - `status: str | None`
    - `coding: list[Coding]` (extracted SNOMED/ICD/LOINC/RxNorm codes)
    - `display_text: str` (human-readable summary of the resource)
    - `raw_json: dict` (original resource, stored for reprocessing)
    - `confidence: float` (1.0 for structured FHIR, < 1.0 for PDF-extracted)
    - `flags: list[str]` (e.g., `"no_date"`, `"unknown_code_system"`)
  - `Coding` (Pydantic model):
    - `system: str` (e.g., `"http://snomed.info/sct"`)
    - `code: str`
    - `display: str | None`

- **PDF extractor** (`crosscures/ingestion/pdf.py`)
  - Stage 1: extract text via PyMuPDF. If text layer is absent or sparse (< 80 chars/page), fall back to Tesseract OCR.
  - Stage 2: send extracted text to LLM with a structured extraction prompt to identify clinical entities (diagnoses, medications, dates, lab values, procedures).
  - Stage 3: map extracted entities to FHIR resource shapes. Set `confidence < 1.0` for all PDF-derived records.
  - Requires `ConsentAction.LLM_INFERENCE` to be granted before calling the LLM extraction step.
  - MVP simplification: no de-identification pre-processing before LLM. Patient consents that their data is sent to the LLM provider under zero-retention agreement. De-identification pipeline is post-MVP.

- **Ingestion service** (`crosscures/ingestion/service.py`)
  - `ingest(request: IngestRequest) -> IngestResult`
    1. `consent_store.require(patient_id, ConsentAction.HEALTH_RECORD_STORAGE)`
    2. Parse based on `source_format`
    3. Deduplicate against existing records by `(resource_id, resource_type)` — skip exact duplicates, flag near-duplicates for review
    4. Persist all extracted `FHIRResource` records to the health record store
    5. Emit `HEALTH_RECORD_INGESTED` event per resource
    6. Return `IngestResult`
  - Errors:
    - `ConsentError`: consent not granted
    - `ParseError`: malformed FHIR JSON or unreadable PDF
    - `DuplicateRecordWarning`: non-fatal, included in `IngestResult.warnings`

---

**Wearable integration (crosscures/wearable/)**

- MVP: Apple HealthKit only. Android / Google Fit deferred.
- Architecture: a native iOS module (Swift, bridged to React Native) requests HealthKit authorization and streams samples to the mobile app layer. The app batches samples and POSTs to the backend sync endpoint.
- `HealthKitSample` (Pydantic model):
  - `sample_id: str` (HealthKit UUID)
  - `patient_id: str`
  - `quantity_type: HealthKitQuantityType` (enum)
  - `value: float`
  - `unit: str`
  - `start_date: datetime`
  - `end_date: datetime`
  - `source_name: str` (device name, e.g., `"Apple Watch Series 9"`)
  - `metadata: dict | None`
- HealthKitQuantityType enum (MVP subset):
  - `HEART_RATE` — bpm
  - `HRV_SDNN` — ms (heart rate variability)
  - `SPO2` — % blood oxygen
  - `STEP_COUNT` — steps
  - `ACTIVE_ENERGY_BURNED` — kcal
  - `SLEEP_ANALYSIS` — categorical (in-bed, asleep, awake)
  - `RESTING_HEART_RATE` — bpm
  - `WALKING_HEART_RATE_AVERAGE` — bpm
  - `RESPIRATORY_RATE` — breaths/min
- Sync strategy:
  - Mobile app syncs on app foreground and on a background task (iOS BGAppRefreshTask, max 1x/15min)
  - Syncs last 7 days of samples on first sync, then incremental (since last sync timestamp)
  - Samples are batched (max 500/request) and compressed (gzip)
  - Deduplication: backend deduplicates by `sample_id`
- `WearableSync` API (backend):
  - `POST /wearable/sync` — accepts `list[HealthKitSample]`, deduplicates, persists, emits `WEARABLE_SYNC_COMPLETED` event
  - Requires `ConsentAction.WEARABLE_SYNC`
- Aggregation: raw samples are never sent to the LLM. The wearable aggregation service computes daily summaries (mean, min, max, stddev per metric per day) and stores them as `WearableDailySummary` records for use in context assembly.
- `WearableDailySummary` (Pydantic model):
  - `patient_id: str`
  - `date: date`
  - `metric: HealthKitQuantityType`
  - `mean: float | None`
  - `min: float | None`
  - `max: float | None`
  - `stddev: float | None`
  - `sample_count: int`
  - `coverage_pct: float` (fraction of the day with data, 0.0–1.0)

---

**Patient profile store (crosscures/store/)**

- Three stores, all per-patient, all encrypted at rest:
  - **Health record store** (PostgreSQL): structured `FHIRResource` rows + raw JSON. Indexed by `(patient_id, resource_type, occurred_at)`.
  - **Event store** (PostgreSQL): immutable append-only event log.
  - **Memory store** (PostgreSQL + pgvector): semantic memory records with embeddings for retrieval. See Memory System below.
- Object storage (S3-compatible): raw uploaded files (FHIR bundles, PDFs, audio transcripts). Keyed as `{patient_id}/{upload_id}/{filename}`. Lifecycle policy: 7-year retention (HIPAA minimum).
- Encryption: all fields marked `PII` in the schema are encrypted at the application layer (AES-256-GCM, per-patient key) before write. Key management via AWS KMS or equivalent.
- Data access: no component accesses the store directly. All reads go through `PatientDataService`, which enforces `patient_id` scoping on every query — no cross-patient reads are possible at the service layer.
- `PatientDataService` API:
  - `get_patient(patient_id: str) -> Patient`
  - `get_records(patient_id: str, resource_types: list[str] | None = None, since: datetime | None = None, limit: int = 100) -> list[FHIRResource]`
  - `get_wearable_summaries(patient_id: str, metrics: list[HealthKitQuantityType] | None = None, since: date | None = None) -> list[WearableDailySummary]`
  - `get_prescriptions(patient_id: str, active_only: bool = True) -> list[Prescription]`
  - `get_symptom_logs(patient_id: str, since: datetime | None = None) -> list[SymptomLog]`

---

**Memory system (crosscures/memory/)**

- Philosophy: the agent must recall what the patient said last Tuesday, what their cardiologist noted three years ago, and what their Apple Watch showed during a symptom spike — all in the same retrieval pass. Memory is hierarchical: structured facts live in the health record store; semantic episodes live in the memory store.
- Memory types:
  - **Semantic memory**: distilled, LLM-generated summaries of health records (e.g., "Patient has Type 2 Diabetes diagnosed in 2019, currently managed with Metformin 1000mg twice daily"). One semantic memory per clinical concept cluster. Updated when new FHIR resources arrive.
  - **Episodic memory**: time-stamped records of patient-reported events (symptom check-ins, clinic sessions, therapy check-ins). Preserved verbatim plus a one-sentence digest.
  - **Wearable memory**: rolling 30-day wearable summaries attached to episodes when relevant (e.g., HRV spike concurrent with symptom report).
  - **Prescription memory**: active medication list with dose, frequency, start date, prescribing physician, and expected outcome timeline.

- `MemoryRecord` (Pydantic model):
  - `memory_id: str` (UUID)
  - `patient_id: str`
  - `memory_type: MemoryType` (`"semantic"`, `"episodic"`, `"wearable"`, `"prescription"`)
  - `content: str` (text content, used for embedding and retrieval)
  - `embedding: list[float] | None` (1536-dim, text-embedding-3-small via OpenAI or equivalent; populated async)
  - `source_event_ids: list[str]` (events that produced this memory)
  - `source_resource_ids: list[str]` (FHIR resource IDs, for citation)
  - `created_at: datetime`
  - `updated_at: datetime`
  - `valid_until: datetime | None` (for time-bounded memories like active prescriptions)
  - `tags: list[str]` (e.g., `["cardiology", "medication", "chronic"]`)
  - `importance: float` (0.0–1.0, used for context window prioritization)

- Memory writer (`crosscures/memory/writer.py`):
  - Triggered by events on the bus: `HEALTH_RECORD_INGESTED` → update semantic memory; `SYMPTOM_CHECKIN_SUBMITTED` → write episodic memory; `PRESCRIPTION_RECORDED` → write prescription memory.
  - `write_semantic_memory(patient_id: str, resource_ids: list[str]) -> MemoryRecord` — clusters related FHIR resources, generates a summary via LLM, embeds, stores.
  - `write_episodic_memory(patient_id: str, event: EventBase) -> MemoryRecord` — serializes the event payload to a human-readable string, embeds, stores.
  - All LLM calls in the writer require `ConsentAction.LLM_INFERENCE`.
  - Embedding is computed asynchronously after write (memory is queryable by structured fields before embedding arrives).

- Memory retriever (`crosscures/memory/retriever.py`):
  - `retrieve(patient_id: str, query: str, top_k: int = 8, memory_types: list[MemoryType] | None = None, recency_weight: float = 0.3) -> list[MemoryRecord]`
    - Embed the query
    - Hybrid search: cosine similarity (semantic) + recency boost + importance weight
    - Filter by `memory_types` if specified
    - Return top-k results, deduplicated by source concept
  - `retrieve_structured(patient_id: str, resource_types: list[str], since: datetime | None = None) -> list[FHIRResource]` — bypass embedding, return raw records by type and date range
  - `retrieve_prescriptions(patient_id: str) -> list[Prescription]` — return active prescriptions with outcome timelines
  - Citation requirement: every `MemoryRecord` returned carries `source_resource_ids`. The agent layer must include citations in any patient-facing or physician-facing output.

- MVP simplifications:
  - Embedding model: OpenAI `text-embedding-3-small`. Provider abstracted behind `EmbeddingProvider` interface for future swap.
  - pgvector with HNSW index used for MVP. Dedicated vector DB (Qdrant, Pinecone) deferred to post-MVP.
  - No memory pruning or forgetting in MVP. All memories accumulate.
  - No memory conflict resolution in MVP: if two records contradict, both are stored and the LLM is prompted to acknowledge uncertainty.

---

**Agent core (crosscures/agent/)**

- The agent is the reasoning layer that assembles context, calls the LLM, validates the response, and routes the output. It is stateless between calls — all state is in the memory store and Redis session cache.

- Agent session lifecycle:
  1. `start_session(patient_id: str, stage: AgentStage, metadata: dict | None = None) -> Session`
  2. `process_turn(session_id: str, input: AgentInput) -> AgentOutput`
  3. `end_session(session_id: str) -> SessionSummary`
  - Sessions are stored in Redis with TTL (stage 1: 30min, stage 2: 4h, stage 3: 30min).

- `AgentStage` enum: `PRE_VISIT`, `CLINIC`, `THERAPY_GUARDIAN`

- `Session` (Pydantic model):
  - `session_id: str`
  - `patient_id: str`
  - `stage: AgentStage`
  - `started_at: datetime`
  - `turns: list[AgentTurn]` (accumulated in Redis)
  - `context_snapshot: dict` (assembled context at session start, immutable for session duration)
  - `metadata: dict | None`

- `AgentInput` (Pydantic model):
  - `content: str` (patient utterance, symptom response, or system-triggered text)
  - `input_type: InputType` (`"patient_utterance"`, `"symptom_response"`, `"system_trigger"`, `"audio_transcript"`)
  - `attachments: list[str] | None` (resource IDs of any records the patient explicitly referenced)
  - `turn_id: str` (UUID, for idempotency)

- `AgentOutput` (Pydantic model):
  - `turn_id: str`
  - `content: str` (agent response)
  - `output_type: OutputType` (`"patient_message"`, `"physician_brief"`, `"physician_alert"`, `"question"`, `"summary"`)
  - `citations: list[Citation]` (memory records cited in the response)
  - `next_action: NextAction | None` (e.g., `{"type": "ask_followup", "question_id": "q_fatigue_duration"}`)
  - `confidence: float` (0.0–1.0, derived from memory coverage of the query)
  - `flagged: bool` (True if response contains uncertain or conflicting information)
  - `llm_call_id: str` (links to audit log entry)

- `Citation` (Pydantic model):
  - `memory_id: str`
  - `source_resource_ids: list[str]`
  - `source_display: str` (e.g., `"MDS-UPDRS assessment, Mayo Clinic, 2024-11-03"`)

- **Context assembly** (`crosscures/agent/context.py`):
  - Called once at session start or per-turn for dynamic sessions (stage 2)
  - `assemble_context(patient_id: str, stage: AgentStage, query: str | None = None) -> AssembledContext`
  - `AssembledContext` (Pydantic model):
    - `patient_summary: str` (semantic memory: demographics, chronic conditions, allergies — always included)
    - `active_medications: list[Prescription]` (prescription memory)
    - `recent_episodes: list[MemoryRecord]` (episodic, last 30 days)
    - `relevant_records: list[MemoryRecord]` (retrieval result for current query)
    - `wearable_summary: str` (last 14-day wearable digest)
    - `active_prescriptions: list[Prescription]`
    - `stage_context: dict` (stage-specific: for CLINIC, includes upcoming appointment details; for THERAPY_GUARDIAN, includes prescription outcome timelines)
    - `total_tokens_estimate: int`
  - Context is assembled to fit within an 80K token budget. If over budget, oldest episodic memories are truncated first, then wearable summary trimmed, then relevant records reduced.

- **LLM interface** (`crosscures/agent/llm.py`):
  - `call_llm(system_prompt: str, messages: list[dict], patient_id: str, purpose: str, max_tokens: int = 2048) -> LLMResponse`
  - `LLMResponse` (Pydantic model):
    - `content: str`
    - `model: str`
    - `input_tokens: int`
    - `output_tokens: int`
    - `latency_ms: int`
    - `call_id: str`
  - Every call is logged to the audit log before returning.
  - Retry: up to 3 attempts with exponential backoff (1s, 2s, 4s) on transient errors (rate limit, timeout). On permanent failure, raise `LLMUnavailableError`.
  - `ConsentAction.LLM_INFERENCE` is checked before every call.
  - Model: `claude-sonnet-4-20250514` in MVP. Model version is pinned in config, not inferred.

- **Response validator** (`crosscures/agent/validator.py`):
  - Validates LLM output before it is returned to the patient or physician.
  - `validate_response(output: str, output_type: OutputType, stage: AgentStage) -> ValidationResult`
  - Checks:
    - No fabricated medication names (cross-reference against patient's active medication list)
    - No dosage instructions (agent must never recommend dose changes)
    - No diagnostic statements framed as conclusions (flagged if output contains `"you have"` + condition name not in confirmed records)
    - No references to records not present in `AssembledContext.source_resource_ids` (hallucination guard)
  - If validation fails: response is flagged, a safety disclaimer is prepended, and the failure is logged.
  - MVP simplification: rule-based checks only. ML-based safety classifier is post-MVP.

- **Audit log** (`crosscures/agent/audit.py`):
  - Immutable append-only table in PostgreSQL.
  - `AuditEntry` (Pydantic model):
    - `entry_id: str`
    - `patient_id: str`
    - `event_type: str` (`"llm_call"`, `"consent_check"`, `"data_access"`, `"physician_delivery"`)
    - `occurred_at: datetime`
    - `payload: dict` (full prompt + completion for `llm_call`, query + record IDs for `data_access`)
    - `actor: str` (`"agent"`, `"patient"`, `"system"`)
    - `session_id: str | None`
  - Retention: 7 years minimum (HIPAA).
  - No reads through application code except for admin audit export endpoint (separate auth).

- Errors:
  - `LLMUnavailableError`: LLM call failed after all retries. Contains `cause` and `retryable: false`.
  - `ContextAssemblyError`: memory retrieval failed or patient has no records. Agent falls back to asking patient directly.
  - `ResponseValidationError`: LLM output failed safety checks. Contains `violation_type` and sanitized output.
  - `SessionExpiredError`: Redis session TTL elapsed. Client must start a new session.

---

**Stage 1 — Pre-Visit Intelligence (crosscures/stages/pre_visit/)**

- Activated by: appointment detected in the patient's calendar (MVP: manual appointment entry in app) with visit date within 14 days.
- Outputs: structured pre-visit physician brief delivered 72h before appointment.

- **Symptom Tracking Engine** (`crosscures/stages/pre_visit/tracker.py`):
  - Manages the daily check-in lifecycle: schedule, question generation, response capture, and storage.
  - `SymptomLog` (Pydantic model):
    - `log_id: str`
    - `patient_id: str`
    - `session_date: date`
    - `questions: list[CheckinQuestion]`
    - `responses: list[CheckinResponse]`
    - `completion_status: Literal["completed", "partial", "skipped"]`
    - `submitted_at: datetime | None`
  - `CheckinQuestion` (Pydantic model):
    - `question_id: str`
    - `text: str`
    - `response_type: ResponseType` (`"scale_1_10"`, `"yes_no"`, `"free_text"`, `"multiple_choice"`, `"duration_picker"`)
    - `domain: SymptomDomain` (enum: `"pain"`, `"fatigue"`, `"mood"`, `"mobility"`, `"sleep"`, `"medication_adherence"`, `"gi"`, `"cardiovascular"`, `"custom"`)
    - `parent_question_id: str | None` (for follow-up questions triggered by prior response)
    - `condition_trigger: str | None` (e.g., `"response.scale >= 7"` — branch condition)
    - `source: Literal["base", "condition_specific", "llm_generated"]`
  - `CheckinResponse` (Pydantic model):
    - `question_id: str`
    - `value: str | int | float | bool | None`
    - `answered_at: datetime`
    - `skipped: bool`

- **Adaptive Question Generator** (`crosscures/stages/pre_visit/question_generator.py`):
  - `generate_checkin(patient_id: str, session_date: date) -> list[CheckinQuestion]`
  - Process:
    1. Load patient's condition list from health records (Condition resources)
    2. Load base question bank (static, condition-agnostic: pain, fatigue, sleep, mood — always present)
    3. For each confirmed condition, inject condition-specific questions from the condition question registry
    4. Call `memory_retriever.retrieve()` to surface any trending concerns from recent episodes
    5. If trending concern detected (same symptom mentioned in 3+ recent logs): generate a targeted follow-up question via LLM
    6. Cap total questions at 12 per session (base: 4, condition-specific: up to 6, LLM-generated: up to 2)
    7. Order: base → condition-specific → LLM-generated
  - Condition question registry: a YAML file mapping ICD/SNOMED codes to question templates. Maintained by clinical team. Not generated by LLM.
  - LLM-generated questions are cached: if the same trending concern exists on consecutive days, the cached question is reused (no redundant LLM call).
  - `ConsentAction.LLM_INFERENCE` required only for the LLM-generated portion.

- **Scheduler** (`crosscures/stages/pre_visit/scheduler.py`):
  - Sends push notifications for daily check-ins.
  - `schedule_checkin(patient_id: str, session_date: date, preferred_time: time) -> ScheduledCheckin`
  - Default time: 8:00 AM patient local time if no preference set.
  - Reminder: if no response within 4h, send one follow-up notification.
  - Pre-appointment window: daily check-ins are activated 14 days before appointment and deactivated after visit.
  - Push: Apple Push Notification Service (APNS) in MVP. FCM deferred.
  - `ScheduledCheckin` (Pydantic model):
    - `checkin_id: str`
    - `patient_id: str`
    - `session_date: date`
    - `scheduled_at: datetime`
    - `notified_at: datetime | None`
    - `reminder_sent_at: datetime | None`
    - `completed_at: datetime | None`

- **Pre-Visit Brief Generator** (`crosscures/stages/pre_visit/brief_generator.py`):
  - Triggered 72h before appointment by the scheduler.
  - `generate_brief(patient_id: str, appointment_id: str) -> PhysicianBrief`
  - Process:
    1. `consent_store.require(patient_id, ConsentAction.PHYSICIAN_BRIEF_SHARING)`
    2. Assemble context: last 14 days of symptom logs + wearable summaries + active medications + relevant health records
    3. Call LLM with structured brief prompt (output format: JSON with sections)
    4. Validate response (no diagnostic conclusions, no dose recommendations)
    5. Construct `PhysicianBrief` and persist
    6. Emit `BRIEF_GENERATED` event
    7. Enqueue for delivery
  - `PhysicianBrief` (Pydantic model):
    - `brief_id: str`
    - `patient_id: str`
    - `appointment_id: str`
    - `generated_at: datetime`
    - `sections: BriefSections`
    - `citations: list[Citation]`
    - `delivery_status: DeliveryStatus`
  - `BriefSections` (Pydantic model):
    - `patient_snapshot: str` (chronic conditions, active medications, known allergies — 3–5 bullets)
    - `symptom_trends: str` (14-day symptom trajectory, notable changes — narrative + data table)
    - `wearable_highlights: str | None` (HRV, sleep, SpO2 anomalies in the window)
    - `medication_adherence: str` (adherence rate per medication, as reported by patient)
    - `patient_concerns: str` (verbatim high-priority patient-reported concerns, quoted)
    - `suggested_discussion_points: list[str]` (3–5 data-backed talking points for physician — not diagnoses)
  - Brief delivery: sent via `BriefDeliveryService` (see Physician Interface). MVP: secure email to physician's registered address. EHR message integration post-MVP.

- MVP simplifications and restrictions:
  - Appointment detection is manual: patient enters appointment date in the app. Calendar integration (Apple Calendar, Google Calendar) is post-MVP.
  - No real-time brief update: brief is generated once at 72h and not regenerated even if new data arrives.
  - No physician feedback loop: physician cannot mark sections as helpful/unhelpful in MVP.

---

**Stage 2 — Clinic Companion (crosscures/stages/clinic/)**

- Activated by: patient explicitly opens a Clinic Session in the app and confirms they are in the clinic.
- Requires: `ConsentAction.AMBIENT_LISTENING` if audio is enabled; `ConsentAction.LLM_INFERENCE`.
- Outputs: real-time contextual responses during the session + structured session summary for physician.

- **Session Manager** (`crosscures/stages/clinic/session_manager.py`):
  - `start_clinic_session(patient_id: str, appointment_id: str | None = None, audio_enabled: bool = False) -> ClinicSession`
  - `ClinicSession` (Pydantic model):
    - `session_id: str`
    - `patient_id: str`
    - `appointment_id: str | None`
    - `started_at: datetime`
    - `audio_enabled: bool`
    - `turns: list[ClinicTurn]`
    - `status: Literal["active", "ended", "abandoned"]`
  - `ClinicTurn` (Pydantic model):
    - `turn_id: str`
    - `speaker: Literal["patient", "agent", "system"]`
    - `content: str`
    - `input_type: InputType`
    - `timestamp: datetime`
    - `citations: list[Citation]`
  - `end_clinic_session(session_id: str) -> ClinicSession`

- **Ambient Listening Module** (`crosscures/stages/clinic/listening.py`):
  - MVP: patient-initiated dictation mode only. Patient taps "speak" to dictate a concern or a physician question; the app transcribes and sends to the agent. Continuous passive transcription (always-on microphone) is post-MVP.
  - STT: on-device Apple Speech framework (SFSpeechRecognizer). Audio is never uploaded; only the transcript text is sent to the backend.
  - `transcribe(audio_data: bytes, language: str = "en-US") -> TranscriptResult`
  - `TranscriptResult` (Pydantic model):
    - `text: str`
    - `confidence: float`
    - `duration_seconds: float`
    - `is_final: bool`
  - Audio is discarded on-device after transcription. No audio bytes are stored anywhere.

- **Context Injection Engine** (`crosscures/stages/clinic/context_engine.py`):
  - On each patient utterance, assembles the most relevant context from memory and constructs a physician-informed response.
  - `process_turn(session_id: str, input: AgentInput) -> AgentOutput`
  - Process per turn:
    1. Retrieve from memory: hybrid search on the patient's utterance (query = `input.content`)
    2. Detect if the utterance is a question directed at the physician (`is_physician_question` classifier — rule-based in MVP: starts with "What about…", "Can you ask…", "Tell them…")
    3. If `is_physician_question`: format the response as a data-backed talking point for the patient to relay, citing the source record
    4. If patient concern: validate against memory, confirm or flag if not supported by records
    5. All responses include one-line citations: `(Source: {source_display})`
  - Safety constraint: the agent never speaks directly to the physician (no third-party audio routing in MVP). It speaks to the patient, who relays information.

- **Conversation Summarizer** (`crosscures/stages/clinic/summarizer.py`):
  - Triggered on `end_clinic_session()`.
  - `summarize_session(session_id: str) -> ClinicSummary`
  - `ClinicSummary` (Pydantic model):
    - `summary_id: str`
    - `session_id: str`
    - `patient_id: str`
    - `generated_at: datetime`
    - `key_discussion_points: list[str]`
    - `patient_concerns_raised: list[str]`
    - `information_provided_to_patient: list[str]`
    - `follow_up_items: list[str]`
    - `citations: list[Citation]`
    - `delivery_status: DeliveryStatus`
  - Emits `CLINIC_SESSION_ENDED` event after summary is generated.
  - The summary is delivered to the physician via `BriefDeliveryService` as a post-visit addendum.
  - The session transcript is written to episodic memory as a `MemoryRecord` with `memory_type="episodic"`.

- MVP simplifications:
  - No real-time physician-facing display during the session (e.g., tablet sidebar). Post-MVP.
  - No multi-participant session support (patient + family member). Single patient session only.
  - Audio never leaves the device. All processing is transcript-based.

---

**Stage 3 — Therapy Guardian (crosscures/stages/therapy/)**

- Activated by: a `PRESCRIPTION_RECORDED` event, which is emitted when the ingestion pipeline extracts a new `MedicationRequest` from health records or the patient manually confirms a new prescription.
- Outputs: physician alert with outcome deviation report, delivered when deviation threshold is breached.

- **Prescription Monitor** (`crosscures/stages/therapy/monitor.py`):
  - Manages the active prescription watchlist and check-in schedule per prescription.
  - `Prescription` (Pydantic model):
    - `prescription_id: str`
    - `patient_id: str`
    - `medication_name: str`
    - `medication_code: str` (RxNorm)
    - `dose: str`
    - `frequency: str`
    - `prescribing_physician: str | None`
    - `start_date: date`
    - `expected_effect_onset_days: int` (how many days before effects are expected — sourced from medication knowledge base)
    - `monitoring_duration_days: int` (how long to actively monitor — default 90 days)
    - `outcome_criteria: list[OutcomeCriterion]`
    - `status: Literal["monitoring", "completed", "deviated", "abandoned"]`
  - `OutcomeCriterion` (Pydantic model):
    - `criterion_id: str`
    - `description: str` (e.g., `"Patient reports pain level ≤ 4/10 by day 14"`)
    - `metric_domain: SymptomDomain`
    - `target_direction: Literal["decrease", "increase", "stabilize"]`
    - `target_threshold: float | None`
    - `assessment_day: int` (day after start to assess this criterion)
  - Outcome criteria are sourced from a static medication-outcome knowledge base (YAML, maintained by clinical team). LLM does not generate outcome criteria in MVP.
  - `start_monitoring(prescription_id: str) -> None` — schedules therapy check-ins and activates monitoring.
  - `stop_monitoring(prescription_id: str, reason: str) -> None` — deactivates watchlist entry.

- **Therapy Check-in** (`crosscures/stages/therapy/checkin.py`):
  - Extends the Stage 1 symptom check-in with prescription-specific questions.
  - Scheduled at: day 3, 7, 14, 30, 60, 90 post-prescription (configurable per medication).
  - `generate_therapy_checkin(patient_id: str, prescription_id: str, day: int) -> list[CheckinQuestion]`
  - Questions are drawn from:
    1. General symptom base (fatigue, pain, mood)
    2. Medication-specific outcome questions (from knowledge base)
    3. Side effect screening questions (from FDA-sourced side effect list per drug class)
  - `TherapyCheckinResponse` extends `SymptomLog` with:
    - `prescription_id: str`
    - `day_since_start: int`
    - `side_effects_reported: list[str]`

- **Outcome Deviation Detector** (`crosscures/stages/therapy/detector.py`):
  - Triggered on every `THERAPY_CHECKIN_SUBMITTED` event.
  - `evaluate_outcomes(patient_id: str, prescription_id: str, checkin: TherapyCheckinResponse) -> OutcomeEvaluation`
  - `OutcomeEvaluation` (Pydantic model):
    - `evaluation_id: str`
    - `prescription_id: str`
    - `assessment_day: int`
    - `criteria_results: list[CriterionResult]`
    - `overall_status: Literal["on_track", "deviating", "deviated"]`
    - `deviation_severity: Literal["mild", "moderate", "severe"] | None`
    - `wearable_correlation: str | None` (e.g., "HRV dropped 18% over same window — may indicate stress response")
  - `CriterionResult` (Pydantic model):
    - `criterion_id: str`
    - `met: bool`
    - `observed_value: float | str | None`
    - `expected_value: float | str | None`
    - `delta: float | None`
  - Deviation thresholds:
    - `mild`: 1–2 criteria missed by ≤ 20% of target
    - `moderate`: 2+ criteria missed or 1 criterion missed by > 20%
    - `severe`: primary outcome criterion missed at the expected assessment day or patient reports a red-flag side effect
  - Red-flag side effects: a curated list per drug class (e.g., chest pain for beta blockers, muscle weakness for statins). Any red-flag report triggers `severe` regardless of other criteria.
  - If `overall_status == "deviated"` or `deviation_severity == "severe"`: emit `OUTCOME_DEVIATION_DETECTED` and trigger alert generation.

- **Alert Generator** (`crosscures/stages/therapy/alert_generator.py`):
  - `generate_alert(patient_id: str, evaluation: OutcomeEvaluation) -> PhysicianAlert`
  - `PhysicianAlert` (Pydantic model):
    - `alert_id: str`
    - `patient_id: str`
    - `prescription_id: str`
    - `generated_at: datetime`
    - `severity: Literal["mild", "moderate", "severe"]`
    - `sections: AlertSections`
    - `citations: list[Citation]`
    - `delivery_status: DeliveryStatus`
    - `requires_acknowledgment: bool` (True if `severity == "severe"`)
  - `AlertSections` (Pydantic model):
    - `patient_snapshot: str`
    - `prescription_summary: str` (medication, dose, start date, prescribing physician)
    - `expected_outcome: str` (what was expected by this day)
    - `observed_outcome: str` (what patient actually reported, with dates)
    - `wearable_evidence: str | None`
    - `deviation_summary: str` (plain-English summary of the gap)
    - `suggested_actions: list[str]` (3–5 options for physician — not orders: "Consider reviewing dose", "Schedule urgent follow-up", etc.)
  - Requires `ConsentAction.PHYSICIAN_ALERT_SHARING` before generating.
  - Emits `ALERT_GENERATED` event.

- MVP simplifications:
  - Prescriptions are extracted from ingested records or manually confirmed by patient. No direct e-prescribing integration.
  - Outcome criteria are static per medication class. No patient-specific calibration in MVP.
  - No patient self-dismissal of alerts. Patient is notified the alert was sent but cannot suppress it.

---

**Physician interface (crosscures/physician/)**

- Web application (Next.js 14, App Router). Physician authentication is separate from patient auth: physicians register with their NPI number, verified against NPPES before account activation.
- Read-only in MVP: physicians view briefs and alerts but cannot write back to the patient record or send in-app messages.

- **Brief Delivery Service** (`crosscures/physician/delivery.py`):
  - `DeliveryStatus` (Pydantic model):
    - `status: Literal["queued", "sent", "delivered", "failed"]`
    - `sent_at: datetime | None`
    - `delivery_method: Literal["email", "ehr_message", "in_app"]`
    - `recipient_address: str` (masked in logs)
    - `error: str | None`
  - `deliver_brief(brief: PhysicianBrief, physician: Physician) -> DeliveryStatus`
  - `deliver_alert(alert: PhysicianAlert, physician: Physician) -> DeliveryStatus`
  - MVP delivery: transactional email via SendGrid (HIPAA-compliant account required). Email contains a secure, time-limited link (JWT, 72h expiry) to view the brief in the web portal. Brief content is not embedded in the email body.
  - Retry: up to 3 delivery attempts with exponential backoff. On permanent failure: status set to `failed`, `ALERT_GENERATED` event re-emitted with `delivery_failed=True` tag for manual intervention.
  - `requires_acknowledgment == True` alerts: if not acknowledged within 24h, a reminder email is sent. If not acknowledged within 48h, the alert is escalated to the clinic's front-desk contact (if registered).

- **Physician dashboard** (web):
  - Routes:
    - `/dashboard` — inbox of unread briefs and unacknowledged alerts, sorted by priority
    - `/patients/{patient_id}/briefs` — all briefs for a patient, newest first
    - `/patients/{patient_id}/alerts` — all alerts, with severity badges and acknowledgment status
    - `/briefs/{brief_id}` — brief detail view with collapsible sections, citations as footnotes
    - `/alerts/{alert_id}` — alert detail with acknowledgment button (POST `/alerts/{alert_id}/acknowledge`)
  - Authentication: physician JWT, 8h session, refresh token with 30-day rolling window
  - Authorization: physicians only see patients who have explicitly linked them in the app. No cross-patient data leakage possible at the API layer.

- **EHR integration adapter** (`crosscures/physician/ehr.py`):
  - MVP: not active. Interface defined for post-MVP implementation.
  - Target: SMART on FHIR R4 (read) + Epic MyChart messaging API (write, for brief/alert delivery as in-basket messages)
  - `EHRAdapter` interface:
    - `send_message(patient_id: str, content: str, message_type: str) -> str` (message ID)
    - `get_appointments(patient_id: str, since: date) -> list[Appointment]`
  - Post-MVP implementations: `EpicAdapter`, `CernerAdapter`

---

**Mobile application (crosscures/mobile/)**

- Platform: iOS only in MVP. React Native 0.74+, Expo SDK 51.
- Native modules: `HealthKitModule` (Swift, bridged via JSI for performance), `SpeechModule` (Apple Speech framework).
- State management: Zustand + React Query. No Redux.
- Offline support: check-in questionnaires are downloaded and cached on-device. Patient can complete a check-in offline; responses are queued and synced when connectivity resumes. The agent is not available offline (requires LLM).
- Biometric authentication: Face ID / Touch ID required to open the app. No passcode fallback in MVP (clinical data warrants biometric-only).

- **Navigation structure**:
  - `/(auth)` — login, registration, consent flows
  - `/(app)/home` — daily check-in card, upcoming appointment countdown, health snapshot
  - `/(app)/checkin` — symptom check-in flow (adaptive questionnaire)
  - `/(app)/clinic` — clinic session flow (stage 2)
  - `/(app)/records` — uploaded health records list, upload new record
  - `/(app)/medications` — active medications, confirm new prescriptions
  - `/(app)/settings` — consent management, linked physician, notification preferences, account

- **Check-in flow**:
  - Fetches questions for today from backend on app open (cached for 24h)
  - Adaptive: if patient answers scale ≥ 7 on pain, next question is a follow-up on pain duration/location
  - Progress bar: patient sees X of N questions remaining
  - Partial saves: each response is auto-saved on answer. If patient closes mid-session, they can resume.
  - Completion triggers `SYMPTOM_CHECKIN_SUBMITTED` event via API.

- **Clinic session flow**:
  - Pre-session: consent confirmation screen (displays `ConsentAction.AMBIENT_LISTENING` if audio enabled)
  - Session: chat-like UI with agent responses. "Speak" button for STT input. Text input always available.
  - Agent responses show citations as tappable footnotes (opens source record detail)
  - End session: patient confirms end. Summary generated async. Patient receives confirmation.

- **Notification strategy**:
  - Daily check-in reminder: silent notification with rich content (today's check-in card)
  - Brief sent to physician: informational push — "Your pre-visit brief has been sent to Dr. {name}"
  - Alert sent to physician: informational push — "Your therapy update has been sent to Dr. {name}"
  - All notification content is generic — no health data in notification payload (visible on lock screen)

---

**Backend API (crosscures/api/)**

- Framework: FastAPI 0.111+, Python 3.12
- Auth: JWT (Auth0). Patient tokens and physician tokens have different scopes. All routes require a valid token.
- All endpoints:
  - Validate JWT, extract `patient_id` or `physician_id` from claims
  - Log request to audit trail (endpoint, actor, timestamp — no payload logging for PII routes)
  - Return structured error responses: `{"error": {"code": str, "message": str, "details": dict | None}}`

- Core routes:

  **Patient routes** (prefix `/v1/patient`):
  - `POST /records/upload` — ingest a FHIR bundle or PDF
  - `GET /records` — list health records by type and date range
  - `GET /wearable/sync-status` — last sync timestamp and sample counts
  - `GET /checkin/today` — fetch today's check-in questions
  - `POST /checkin/response` — submit a check-in response batch
  - `POST /clinic/session/start` — start a clinic session
  - `POST /clinic/session/{session_id}/turn` — process one conversation turn
  - `POST /clinic/session/{session_id}/end` — end session and trigger summary
  - `GET /prescriptions` — list active prescriptions
  - `POST /prescriptions/{prescription_id}/confirm` — patient confirms a detected prescription
  - `GET /consent` — list all consent records
  - `POST /consent/grant` — grant a consent action
  - `POST /consent/revoke` — revoke a consent action

  **Physician routes** (prefix `/v1/physician`):
  - `GET /patients` — list linked patients
  - `GET /patients/{patient_id}/briefs` — list briefs for a patient
  - `GET /briefs/{brief_id}` — brief detail
  - `GET /patients/{patient_id}/alerts` — list alerts
  - `GET /alerts/{alert_id}` — alert detail
  - `POST /alerts/{alert_id}/acknowledge` — acknowledge an alert

  **Wearable sync route** (called from mobile native module):
  - `POST /v1/wearable/sync` — accept batched HealthKit samples

- Rate limiting: 60 req/min per patient token on patient routes, 120 req/min on physician routes. Redis-backed sliding window.
- CORS: only `crosscures.ai` and `*.crosscures.ai` origins permitted.

---

**Privacy, security, and compliance (crosscures/security/)**

- HIPAA technical safeguards:
  - Encryption at rest: AES-256-GCM. All PostgreSQL columns marked `[ENCRYPTED]` are encrypted at application layer before write, decrypted after read. Key per patient, managed by AWS KMS.
  - Encryption in transit: TLS 1.3 for all API traffic, internal service-to-service, and database connections.
  - Audit controls: every access to patient data is logged in the audit log (actor, timestamp, record IDs accessed). Logs are write-once, tamper-evident (hash chaining in MVP; dedicated WORM store post-MVP).
  - Automatic logoff: mobile app locks after 15 minutes of inactivity. Web portal session expires after 8 hours.
  - Emergency access: break-glass access procedure defined (separate admin role, requires 2-person authorization, full audit trail).
- BAA requirements: signed BAA required with Anthropic (LLM inference), SendGrid (email delivery), AWS (infrastructure), and Auth0 (authentication) before any patient data flows through these services.
- Vulnerability management: OWASP Top 10 mitigated by design. Dependency scanning (Snyk) on every CI run. Penetration test required before clinical pilot launch.
- De-identification: all data used for model improvement must be de-identified per HIPAA Safe Harbor (18 identifiers removed) before use. Requires `ConsentAction.RESEARCH_DATA_USE`. Deferred to post-MVP.

---

**Implementation order**

1. Consent system and `ConsentStore` — every subsequent component depends on this; must be first
2. Auth layer (patient + physician JWT, Auth0 integration), base API scaffolding (FastAPI, error handling, audit log skeleton)
3. Event bus (PostgreSQL outbox, typed events, dispatcher)
4. Patient profile store (`PatientDataService`, encryption layer, S3 object storage)
5. Health record ingestion (FHIR R4 parser, `FHIRResource` model, ingestion service — FHIR JSON only first)
6. PDF extractor (PyMuPDF + Tesseract OCR + LLM extraction — requires LLM interface)
7. LLM interface (`call_llm`, retry, audit log integration) and response validator (rule-based safety checks)
8. Wearable integration (HealthKit iOS native module, batch sync endpoint, `WearableDailySummary` aggregation)
9. Memory system (memory store schema, pgvector, embedding pipeline, `MemoryWriter`, `MemoryRetriever`)
10. Agent core (context assembly, session lifecycle, `process_turn`, `AssembledContext`)
11. Stage 1 — Symptom Tracking: question bank, adaptive generator, scheduler, push notifications (APNS)
12. Stage 1 — Pre-Visit Brief: brief generator, `BriefSections` schema, LLM brief prompt, `BriefDeliveryService` (email)
13. Mobile app — core flows: auth, home, check-in questionnaire, records upload, consent management
14. Stage 2 — Clinic Companion: session manager, STT (Apple Speech), context injection engine, session summarizer
15. Stage 3 — Therapy Guardian: prescription monitor, knowledge base (YAML), therapy check-in, outcome deviation detector, alert generator
16. Physician web dashboard: Next.js app, brief viewer, alert inbox, acknowledgment flow
17. EHR integration adapter (interface only — no active implementation in MVP)
18. End-to-end integration tests: ingest → memory → check-in → brief → delivery; prescription → deviation → alert → acknowledgment
19. Security hardening: penetration test, audit log tamper-evidence, encryption key rotation procedure
20. Clinical pilot preparation: IRB documentation, pilot site onboarding runbook, on-call escalation procedure

---

**Acceptance checklist**

- Consent system enforces all six `ConsentAction` types; every sensitive call site calls `consent_store.require()` before proceeding
- Revocation of any consent action takes effect within one request cycle; no cached consent state persists beyond the current request
- FHIR R4 parser correctly extracts all 10 supported resource types; unsupported types produce a warning and are skipped, not silently dropped
- PDF extractor correctly extracts medications, diagnoses, and lab values from a representative sample of clinical note formats; low-confidence extractions are flagged
- Wearable sync is idempotent: re-submitting the same HealthKit sample batch produces no duplicate records
- `WearableDailySummary` aggregation is correct for all 9 supported HealthKit quantity types
- All patient data reads go through `PatientDataService`; no component bypasses the service layer to query the DB directly
- Memory writer correctly triggers on all four event types; all written `MemoryRecord`s have valid embeddings within 30s of write
- Memory retriever returns results ranked by hybrid score (semantic + recency + importance); same query on same data produces identical ranked results
- LLM interface retries exactly 3 times on transient errors; permanent errors raise `LLMUnavailableError` immediately
- Every LLM call produces an `AuditEntry` with full prompt, completion, model version, token counts, and latency
- Response validator correctly flags: fabricated medication names, dosage instructions, ungrounded diagnostic conclusions
- Stage 1 check-in generates between 4 and 12 questions; base questions always present; condition-specific questions appear only for patients with confirmed matching conditions
- Adaptive questioning: a scale ≥ 7 response on a pain question triggers the pain follow-up branch question
- Pre-visit brief is generated exactly once, 72h before appointment; regeneration on demand raises `BriefAlreadyGeneratedError`
- All six `BriefSections` fields are populated; `wearable_highlights` is `null` only when the patient has no wearable data in the window
- Citations are present on every brief and alert; each citation links to a specific source `FHIRResource` or `MemoryRecord`
- Clinic session: on-device STT produces a transcript without any audio bytes leaving the device; backend receives only text
- Stage 2 session turns correctly cite the source record for every factual claim in the agent response
- Clinic session summary is written to episodic memory as a `MemoryRecord` within 60s of `end_clinic_session()`
- Stage 3 prescription monitoring activates within one event cycle of `PRESCRIPTION_RECORDED`
- Outcome deviation detector correctly classifies `mild`, `moderate`, and `severe` deviations against the threshold definitions
- Red-flag side effect report triggers `severe` classification regardless of all other criteria
- Physician alert is delivered via email within 5 minutes of `ALERT_GENERATED` event
- `requires_acknowledgment == True` alerts send a reminder at 24h and escalate at 48h if unacknowledged
- Physician dashboard only shows patients explicitly linked by that patient; cross-patient data access is not possible at the API layer
- All PostgreSQL columns marked `[ENCRYPTED]` are unreadable as plaintext in the database; decryption only occurs at application layer
- Audit log is append-only; no `UPDATE` or `DELETE` is possible on audit entries via any application code path
- Mobile app locks after 15 minutes of inactivity; biometric re-authentication is required to unlock
- Rate limiting enforced: patient tokens blocked after 60 req/min; physician tokens after 120 req/min
- All check-in responses are saved incrementally; patient can resume a partial check-in after app close
- Offline check-in: questionnaire available and submittable without network; responses sync on next connectivity
- Full end-to-end test: patient uploads FHIR bundle → ingested into records → memory writer produces semantic memory → 72h before appointment, brief is generated citing those records → delivered to physician → physician views and acknowledges brief
- Full end-to-end test: prescription recorded → therapy check-in scheduled at day 7 → patient reports deviation → outcome deviation detected → physician alert generated and delivered → physician acknowledges within 24h

---

**Non-functional requirements**

- Security: all patient data encrypted at rest (AES-256-GCM, per-patient key via KMS) and in transit (TLS 1.3). BAA signed with all sub-processors before any patient data flows. No plaintext PII in application logs. Secrets managed via AWS Secrets Manager; no secrets in environment variables or source code.
- Performance: pre-visit brief generation (LLM call + context assembly) completes within 30s. Stage 2 turn response (retrieval + LLM) completes within 5s. Wearable sync of 500 samples processes within 3s. All patient-facing API endpoints respond within 1s for non-LLM routes.
- Reliability: core API target 99.9% uptime. LLM inference failures degrade gracefully (agent acknowledges unavailability, does not fail silently). Brief and alert delivery retried with exponential backoff; failures do not cause data loss.
- Scalability: stateless API servers horizontally scalable behind a load balancer. PostgreSQL read replicas for physician dashboard queries. Memory store (pgvector) partitioned per patient for isolation. Event bus worker pool scales independently of API servers.
- Observability: structured JSON logging (patient_id masked as hash in logs). Distributed tracing (OpenTelemetry) across API, agent, and delivery services. Metrics: LLM latency, token consumption, check-in completion rate, brief delivery success rate, alert acknowledgment rate — all tracked in Grafana. Alert on: LLM error rate > 1%, brief delivery failure rate > 0.1%, any `ConsentError` in production (unexpected consent gap).
- Data residency: all patient data stored in AWS us-east-1 in MVP. Multi-region deferred. Data residency must be configurable per health system partner for post-MVP international expansion.
- Extensibility: `EmbeddingProvider` interface allows swap of embedding model without changing memory system. `EHRAdapter` interface allows adding Epic/Cerner without changing agent core. `DeliveryService` interface allows adding EHR message delivery without changing brief/alert generators. Condition question registry and medication outcome knowledge base are YAML files, updatable by clinical team without code changes.
- Auditability: full prompt-response pairs retained for 7 years. Audit log exportable per patient for HIPAA Right of Access requests. Consent history exportable. All events in the event log are the source of truth for any dispute about what data the agent accessed or sent.
