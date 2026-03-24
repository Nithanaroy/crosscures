"""
Checkin Controller - Route handlers for check-in API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from models import (
    CheckinQuestion,
    CheckinResponse,
    CheckinSession,
    CheckinSummary,
    GeneratorMode,
)
from services import (
    StaticQuestionnaireGenerator,
    LLMQuestionnaireGenerator,
    llm_is_available,
    llm_available_models,
)
from repositories import (
    PatientDataProvider,
    MockPatientDataProvider,
    DuckDBPatientDataProvider,
    SessionStore,
)


router = APIRouter()

# Global services — dual generators
static_generator = StaticQuestionnaireGenerator()
llm_generator = LLMQuestionnaireGenerator()
session_store = SessionStore()
patient_data_provider: Optional[PatientDataProvider] = None


# ============================================================================
# Initialization
# ============================================================================

def initialize_provider():
    """Initialize data provider (mock by default)"""
    global patient_data_provider
    if patient_data_provider is None:
        patient_data_provider = MockPatientDataProvider()


def set_data_provider(provider: PatientDataProvider):
    """Allow runtime switching of data provider"""
    global patient_data_provider
    patient_data_provider = provider


# ============================================================================
# Request/Response Models
# ============================================================================

class InitializeCheckinRequest(BaseModel):
    patient_id: str
    mode: str = "static"  # "static" or "llm"
    model: Optional[str] = None  # OpenRouter model ID override


class QuestionTreeNode(BaseModel):
    question_id: str
    question_text: str
    condition_tag: str
    question_type: str
    depends_on_question_id: Optional[str] = None
    depends_on_response: Optional[str] = None
    trigger_label: Optional[str] = None


class InitializeCheckinResponse(BaseModel):
    session_id: str
    patient_name: str
    patient_id: str
    conditions: list[str]
    medications: list[str]
    total_questions: int
    first_question: CheckinQuestion
    question_tree: list[QuestionTreeNode]
    mode: str = "static"
    first_reasoning: Optional[str] = None


class SubmitResponseRequest(BaseModel):
    session_id: str
    response: CheckinResponse


class SubmitResponseResponse(BaseModel):
    message: str
    next_question: Optional[CheckinQuestion] = None
    is_complete: bool = False
    skipped_questions: list[str] = []
    reasoning: Optional[str] = None
    updated_question_tree: Optional[list[QuestionTreeNode]] = None


class CompleteCheckinRequest(BaseModel):
    session_id: str


class PatientInfoResponse(BaseModel):
    patient_id: str
    name: str
    conditions: list[str]
    medications: list[str]


class DataSourceStatus(BaseModel):
    provider_type: str
    description: str


# ============================================================================
# Health & Data Source Endpoints
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/data-source", response_model=DataSourceStatus)
async def get_data_source():
    """Get current data provider"""
    initialize_provider()
    
    if isinstance(patient_data_provider, MockPatientDataProvider):
        return DataSourceStatus(
            provider_type="mock",
            description="Using mock patient data"
        )
    elif isinstance(patient_data_provider, DuckDBPatientDataProvider):
        return DataSourceStatus(
            provider_type="duckdb",
            description="Using DuckDB patient data"
        )
    return DataSourceStatus(
        provider_type="unknown",
        description="Unknown data provider"
    )


@router.post("/data-source/switch-to-mock")
async def switch_to_mock():
    """Switch to mock data provider"""
    set_data_provider(MockPatientDataProvider())
    return {"message": "Switched to mock data provider"}


@router.post("/data-source/switch-to-duckdb")
async def switch_to_duckdb(db_path: str = Query(...)):
    """Switch to DuckDB provider"""
    try:
        set_data_provider(DuckDBPatientDataProvider(db_path))
        return {"message": f"Switched to DuckDB provider: {db_path}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Patient Endpoints
# ============================================================================

@router.get("/patients")
async def list_patients() -> list[PatientInfoResponse]:
    """List available patients"""
    initialize_provider()
    
    patients = patient_data_provider.list_all_patients()
    return [
        PatientInfoResponse(
            patient_id=p.patient_id,
            name=p.name,
            conditions=[c.condition_name for c in p.conditions],
            medications=p.current_medications,
        )
        for p in patients
    ]


@router.get("/patients/{patient_id}", response_model=PatientInfoResponse)
async def get_patient(patient_id: str):
    """Get patient info"""
    initialize_provider()
    
    patient = patient_data_provider.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return PatientInfoResponse(
        patient_id=patient.patient_id,
        name=patient.name,
        conditions=[c.condition_name for c in patient.conditions],
        medications=patient.current_medications,
    )


# ============================================================================
# Check-in Endpoints
# ============================================================================

@router.post("/checkin/initialize", response_model=InitializeCheckinResponse)
async def initialize_checkin(request: InitializeCheckinRequest):
    """Initialize a new check-in session"""
    initialize_provider()
    
    patient = patient_data_provider.get_patient(request.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Select generator based on mode
    mode = request.mode if request.mode in ("static", "llm") else "static"
    if mode == "llm" and not llm_is_available():
        raise HTTPException(status_code=400, detail="LLM mode unavailable: OPENROUTER_API_KEY not set")
    
    gen = llm_generator if mode == "llm" else static_generator
    
    # Generate adaptive questionnaire
    if mode == "llm":
        questions = gen.generate_questionnaire(patient, model=request.model)
    else:
        questions = gen.generate_questionnaire(patient)
    
    # Create session
    session_id = str(uuid.uuid4())
    session = CheckinSession(
        session_id=session_id,
        patient_id=request.patient_id,
        created_at=datetime.now(),
        all_questions=questions,
        current_question_index=0,
        generator_mode=mode,
        llm_model=request.model,
    )
    
    session_store.create_session(session_id, {"session": session})
    
    # Get first question
    first_question, actual_index, reasoning = gen.get_next_question(
        patient,
        questions,
        [],
        0
    )
    session.current_question_index = actual_index
    session_store.update_session(session_id, {"session": session})
    
    if not first_question:
        raise HTTPException(status_code=500, detail="Failed to generate questionnaire questions")
    
    # Build question tree for the decision tree panel
    question_tree = _build_question_tree(questions)
    
    return InitializeCheckinResponse(
        session_id=session_id,
        patient_name=patient.name,
        patient_id=patient.patient_id,
        conditions=[c.condition_name for c in patient.conditions],
        medications=patient.current_medications,
        total_questions=len(questions),
        first_question=first_question,
        question_tree=question_tree,
        mode=mode,
        first_reasoning=reasoning,
    )


@router.post("/checkin/submit-response", response_model=SubmitResponseResponse)
async def submit_response(request: SubmitResponseRequest):
    """Submit a response to a question"""
    initialize_provider()
    
    session_data = session_store.get_session(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session: CheckinSession = session_data["session"]
    patient = patient_data_provider.get_patient(session.patient_id)
    
    # Select generator based on session mode
    gen = llm_generator if session.generator_mode == "llm" else static_generator
    
    # Record response
    session.responses.append(request.response)
    
    # Move to next question
    next_index = session.current_question_index + 1
    if session.generator_mode == "llm":
        next_question, actual_index, reasoning = gen.get_next_question(
            patient,
            session.all_questions,
            session.responses,
            next_index,
            model=session.llm_model,
        )
    else:
        next_question, actual_index, reasoning = gen.get_next_question(
            patient,
            session.all_questions,
            session.responses,
            next_index
        )
    
    # Collect skipped question IDs (those between next_index and actual_index)
    skipped = []
    if next_question is not None:
        for i in range(next_index, actual_index):
            skipped.append(session.all_questions[i].question_id)
    else:
        # Questionnaire is done - remaining questions with unmet deps are skipped
        for i in range(next_index, len(session.all_questions)):
            q = session.all_questions[i]
            if q.depends_on_question_id:
                skipped.append(q.question_id)
    
    is_complete = next_question is None
    if not is_complete:
        session.current_question_index = actual_index
    
    session_store.update_session(session.session_id, {"session": session})
    
    # Build updated tree if LLM mode (plan may have changed)
    updated_tree = None
    if session.generator_mode == "llm":
        updated_tree = _build_question_tree(session.all_questions)
    
    return SubmitResponseResponse(
        message="Response recorded" if not is_complete else "Questionnaire complete",
        next_question=next_question,
        is_complete=is_complete,
        skipped_questions=skipped,
        reasoning=reasoning,
        updated_question_tree=updated_tree,
    )


@router.get("/checkin/{session_id}")
async def get_session(session_id: str):
    """Get current session state"""
    
    session_data = session_store.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session: CheckinSession = session_data["session"]
    
    return {
        "session_id": session.session_id,
        "patient_id": session.patient_id,
        "created_at": session.created_at.isoformat(),
        "current_question_index": session.current_question_index,
        "total_questions": len(session.all_questions),
        "responses_count": len(session.responses),
        "is_complete": session.current_question_index >= len(session.all_questions),
    }


@router.post("/checkin/complete")
async def complete_checkin(request: CompleteCheckinRequest):
    """Complete check-in and generate summary"""
    
    session_data = session_store.get_session(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session: CheckinSession = session_data["session"]
    session.completed_at = datetime.now()
    
    # Generate summary
    responses_dict = {r.question_id: r.response_value for r in session.responses}
    duration = (session.completed_at - session.created_at).total_seconds() / 60
    
    # Find questions for summary context
    summary_text = "Check-in completed successfully.\n\n"
    for resp in session.responses:
        question = next(
            (q for q in session.all_questions if q.question_id == resp.question_id),
            None
        )
        if question:
            summary_text += f"Q: {question.question_text}\nA: {resp.response_value}\n\n"
    
    summary = CheckinSummary(
        session_id=session.session_id,
        patient_id=session.patient_id,
        responses=responses_dict,
        duration_minutes=duration,
        completed_at=session.completed_at,
        notes=summary_text,
    )
    
    session_store.update_session(session.session_id, {
        "session": session,
        "summary": summary
    })
    
    return {
        "summary": summary,
        "message": f"Check-in completed in {duration:.1f} minutes with {len(session.responses)} responses",
    }


@router.get("/checkin/{session_id}/summary")
async def get_summary(session_id: str):
    """Get check-in summary"""
    
    session_data = session_store.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    summary = session_data.get("summary")
    if not summary:
        raise HTTPException(status_code=400, detail="Check-in not completed")
    
    return summary


# ============================================================================
# Helpers
# ============================================================================

def _build_question_tree(questions: list[CheckinQuestion]) -> list[QuestionTreeNode]:
    """Build question tree nodes for the frontend decision tree panel"""
    nodes = []
    for q in questions:
        trigger_label = None
        if q.depends_on_question_id:
            meta = q.metadata or {}
            if meta.get("trigger_type") == "threshold":
                op = meta.get("threshold_operator", ">=")
                val = meta.get("threshold_value", "?")
                trigger_label = f"if {op} {val}"
            elif q.depends_on_response is True:
                trigger_label = "if Yes"
            elif q.depends_on_response is False:
                trigger_label = "if No"
            else:
                trigger_label = f"if {q.depends_on_response}"

        nodes.append(QuestionTreeNode(
            question_id=q.question_id,
            question_text=q.question_text,
            condition_tag=q.condition_tag,
            question_type=q.question_type.value,
            depends_on_question_id=q.depends_on_question_id,
            depends_on_response=str(q.depends_on_response) if q.depends_on_response is not None else None,
            trigger_label=trigger_label,
        ))
    return nodes


# ============================================================================
# Utility Endpoints
# ============================================================================

@router.get("/questions/bank")
async def get_question_bank() -> dict:
    """Get all available questions (for debugging/demo purposes)"""
    questions = static_generator.question_bank.questions
    return {
        "total_questions": len(questions),
        "by_condition": {
            "base": len(static_generator.question_bank.get_questions_by_condition("base")),
            "diabetes": len(static_generator.question_bank.get_questions_by_condition("diabetes")),
            "hypertension": len(static_generator.question_bank.get_questions_by_condition("hypertension")),
            "cardiac": len(static_generator.question_bank.get_questions_by_condition("cardiac")),
            "respiratory": len(static_generator.question_bank.get_questions_by_condition("respiratory")),
        },
        "questions": questions,
    }


@router.get("/generator/status")
async def generator_status() -> dict:
    """Report which generator modes are available and list models"""
    return {
        "static": True,
        "llm": llm_is_available(),
        "models": llm_available_models(),
    }
