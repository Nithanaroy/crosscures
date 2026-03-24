"""
Stage 1 MVP - Pydantic Schemas (Model Layer)
Defines all data structures used in the application.
"""
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class QuestionType(str, Enum):
    """Supported question types for adaptive questionnaire"""
    YES_NO = "yes_no"
    SCALE_1_10 = "scale_1_10"
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"


class GeneratorMode(str, Enum):
    """Which question generation engine to use"""
    STATIC = "static"
    LLM = "llm"


class CheckinQuestion(BaseModel):
    """Single adaptive questionnaire question"""
    question_id: str
    question_text: str
    question_type: QuestionType
    condition_tag: str = Field(default="base", description="Which condition this applies to (base, diabetes, hypertension, etc)")
    depends_on_question_id: Optional[str] = None
    depends_on_response: Optional[Any] = None  # What response value triggers this question
    options: Optional[list[str]] = None  # For multiple_choice
    metadata: dict = Field(default_factory=dict)
    rationale: Optional[str] = None  # LLM reasoning for why this question was chosen


class CheckinResponse(BaseModel):
    """Patient's response to a question"""
    question_id: str
    response_value: Any


class PatientCondition(BaseModel):
    """Patient's confirmed condition for filtering questions"""
    condition_name: str
    condition_code: Optional[str] = None
    onset_date: Optional[datetime] = None
    status: str = "active"  # active, resolved, etc


class PatientProfile(BaseModel):
    """Minimal patient profile for demo"""
    patient_id: str
    name: str
    conditions: list[PatientCondition] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    last_visit_date: Optional[datetime] = None


class CheckinSession(BaseModel):
    """Session for a single check-in"""
    session_id: str
    patient_id: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    responses: list[CheckinResponse] = Field(default_factory=list)
    current_question_index: int = 0
    all_questions: list[CheckinQuestion] = Field(default_factory=list)
    generator_mode: str = "static"
    llm_model: Optional[str] = None


class CheckinSummary(BaseModel):
    """Summary of completed check-in"""
    session_id: str
    patient_id: str
    responses: dict[str, Any]  # question_id -> response_value
    duration_minutes: float
    completed_at: datetime
    notes: str = ""
