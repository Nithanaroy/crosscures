"""Pydantic models for the offline eval pipeline."""
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# DB entity models
# ---------------------------------------------------------------------------

class EvalCase(BaseModel):
    case_id: str
    patient_id: int
    cutoff_date: str
    case_domain: str
    case_name: str
    note_ids_included: list[int]
    input_summary: str = ""


class HistoryTarget(BaseModel):
    target_id: str
    case_id: str
    patient_id: int
    case_domain: str
    concept: str
    target_slot: str
    patient_answerable: str = "yes"
    severity: str = ""
    weight: int = 1
    source_note_ids: list[int] = []
    rationale: str = ""


class LinkedOutcome(BaseModel):
    outcome_id: str
    case_id: str
    patient_id: int
    case_domain: str
    concept: str
    event_type: str
    severity: str = ""
    source_note_ids: list[int] = []
    outcome_detail: str = ""


# ---------------------------------------------------------------------------
# Pipeline models
# ---------------------------------------------------------------------------

class CaseInput(BaseModel):
    case_id: str
    patient_id: int
    cutoff_date: str
    case_domain: str
    case_name: str
    note_count: int
    notes_text: str
    char_count: int


class GeneratedQuestions(BaseModel):
    """Structured output schema for LLM question generation."""
    questions: list[str]


class RawQuestion(BaseModel):
    rank: int
    raw: str


class UsageInfo(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GenerationMeta(BaseModel):
    model: str
    system_prompt: str
    user_prompt: str
    raw_output: str
    input_chars: int
    usage: UsageInfo


class NormalizedQuestionItem(BaseModel):
    """Single item in the structured output from the normalizer LLM."""
    rank: int
    raw: str
    domain: str
    concept: str
    target_slot: str
    grounded: bool


class NormalizedQuestionList(BaseModel):
    """Structured output schema for LLM normalization."""
    questions: list[NormalizedQuestionItem]


class NormalizedQuestion(BaseModel):
    rank: int
    raw: str
    domain: str
    concept: str
    target_slot: str
    grounded: bool
    matched_target_id: str | None = None


class CaseScores(BaseModel):
    coverage: float
    weighted_coverage: float
    grounded_precision: float
    top_5_coverage: float
    top_10_coverage: float
    matched_count: int
    total_targets: int
    total_generated: int


class TargetDetail(BaseModel):
    target_id: str
    concept: str
    target_slot: str
    severity: str
    weight: int
    hit: bool
    matched_by: str | None = None
    matched_rank: int | None = None


class UnmatchedQuestion(BaseModel):
    rank: int | None = None
    raw: str | None = None
    domain: str | None = None
    concept: str | None = None
    target_slot: str | None = None


class MatchResult(BaseModel):
    scores: CaseScores
    target_detail: list[TargetDetail]
    unmatched_questions: list[UnmatchedQuestion]


class AggregateScores(BaseModel):
    coverage: float = 0.0
    weighted_coverage: float = 0.0
    grounded_precision: float = 0.0
    top_5_coverage: float = 0.0
    top_10_coverage: float = 0.0
    total_cases: int = 0
    total_targets: int = 0
    total_matched: int = 0


class CaseResult(BaseModel):
    case_id: str
    case_domain: str
    case_name: str
    note_count: int
    char_count: int
    generated_questions: list[NormalizedQuestion]
    scores: CaseScores
    target_detail: list[TargetDetail]
    unmatched_questions: list[UnmatchedQuestion]
    gen_meta: GenerationMeta


class PipelineConfig(BaseModel):
    provider: str
    model: str
    normalizer_model: str
    temperature: float


class PipelineOutput(BaseModel):
    run_timestamp: str
    config: PipelineConfig
    aggregate_scores: AggregateScores
    case_results: list[CaseResult]
