"""
Checkin Controller - Route handlers for check-in API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from crosscures.models import (
    CheckinQuestion,
    CheckinResponse,
    CheckinSession,
    CheckinSummary,
)
from crosscures.services import AdaptiveQuestionnaireGenerator
from crosscures.repositories import (
    PatientDataProvider,
    MockPatientDataProvider,
    DuckDBPatientDataProvider,
    SessionStore,
)


router = APIRouter()

# Global services
generator = AdaptiveQuestionnaireGenerator()
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


class InitializeCheckinResponse(BaseModel):
    session_id: str
    patient_name: str
    total_questions: int
    first_question: CheckinQuestion


class SubmitResponseRequest(BaseModel):
    session_id: str
    response: CheckinResponse


class SubmitResponseResponse(BaseModel):
    message: str
    next_question: Optional[CheckinQuestion] = None
    is_complete: bool = False


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
    
    # Generate adaptive questionnaire
    questions = generator.generate_questionnaire(patient)
    
    # Create session
    session_id = str(uuid.uuid4())
    session = CheckinSession(
        session_id=session_id,
        patient_id=request.patient_id,
        created_at=datetime.now(),
        all_questions=questions,
        current_question_index=0,
    )
    
    session_store.create_session(session_id, {"session": session})
    
    # Get first question
    first_question, actual_index = generator.get_next_question(
        patient,
        questions,
        [],
        0
    )
    session.current_question_index = actual_index
    session_store.update_session(session_id, {"session": session})
    
    return InitializeCheckinResponse(
        session_id=session_id,
        patient_name=patient.name,
        total_questions=len(questions),
        first_question=first_question,
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
    
    # Record response
    session.responses.append(request.response)
    
    # Move to next question
    next_index = session.current_question_index + 1
    next_question, actual_index = generator.get_next_question(
        patient,
        session.all_questions,
        session.responses,
        next_index
    )
    
    is_complete = next_question is None
    if not is_complete:
        session.current_question_index = actual_index
    
    session_store.update_session(session.session_id, {"session": session})
    
    return SubmitResponseResponse(
        message="Response recorded" if not is_complete else "Questionnaire complete",
        next_question=next_question,
        is_complete=is_complete,
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
# Utility Endpoints
# ============================================================================

@router.get("/questions/bank")
async def get_question_bank() -> dict:
    """Get all available questions (for debugging/demo purposes)"""
    questions = generator.question_bank.questions
    return {
        "total_questions": len(questions),
        "by_condition": {
            "base": len(generator.question_bank.get_questions_by_condition("base")),
            "diabetes": len(generator.question_bank.get_questions_by_condition("diabetes")),
            "hypertension": len(generator.question_bank.get_questions_by_condition("hypertension")),
            "cardiac": len(generator.question_bank.get_questions_by_condition("cardiac")),
            "respiratory": len(generator.question_bank.get_questions_by_condition("respiratory")),
        },
        "questions": questions,
    }
