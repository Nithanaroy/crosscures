"""
Stage 1 MVP - Adaptive Question Generator (Service Layer)
Provides a QuestionnaireGenerator interface with two implementations:
  - StaticQuestionnaireGenerator: hardcoded question bank with branching logic
  - LLMQuestionnaireGenerator: LLM-powered personalized generation via OpenRouter
"""
import json
import logging
from abc import ABC, abstractmethod
from models.schemas import CheckinQuestion, CheckinResponse, PatientProfile, QuestionType
from services.llm.provider import LLMProvider
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Abstract Interface
# ============================================================================

class QuestionnaireGenerator(ABC):
    """Interface for question generation engines."""

    @abstractmethod
    def generate_questionnaire(self, patient: PatientProfile) -> list[CheckinQuestion]:
        """Generate a personalized list of questions for the patient."""
        ...

    @abstractmethod
    def get_next_question(
        self,
        patient: PatientProfile,
        all_available_questions: list[CheckinQuestion],
        responses_so_far: list[CheckinResponse],
        current_index: int,
    ) -> tuple[Optional[CheckinQuestion], int, Optional[str]]:
        """
        Get the next question to ask.
        Returns (question, actual_index, reasoning).
        reasoning is None for static mode, a CoT string for LLM mode.
        """
        ...



class QuestionBank:
    """Repository of all available questions"""
    
    def __init__(self):
        self.questions = self._build_question_bank()
    
    def _build_question_bank(self) -> list[CheckinQuestion]:
        """Build comprehensive question bank with base and condition-specific questions"""
        
        questions = [
            # === BASE QUESTIONS (always included) ===
            CheckinQuestion(
                question_id="base_001",
                question_text="How would you rate your overall health today? (1=Poor, 10=Excellent)",
                question_type=QuestionType.SCALE_1_10,
                condition_tag="base",
            ),
            CheckinQuestion(
                question_id="base_002",
                question_text="Have you experienced any new symptoms or health concerns since your last visit?",
                question_type=QuestionType.YES_NO,
                condition_tag="base",
            ),
            CheckinQuestion(
                question_id="base_003_detail",
                question_text="Please describe the new symptoms or concerns:",
                question_type=QuestionType.TEXT,
                condition_tag="base",
                depends_on_question_id="base_002",
                depends_on_response=True,
            ),
            CheckinQuestion(
                question_id="base_004",
                question_text="How would you rate any pain or discomfort you're experiencing? (1=None, 10=Severe)",
                question_type=QuestionType.SCALE_1_10,
                condition_tag="base",
            ),
            CheckinQuestion(
                question_id="base_005_detail",
                question_text="Where is the pain/discomfort located?",
                question_type=QuestionType.TEXT,
                condition_tag="base",
                depends_on_question_id="base_004",
                depends_on_response=7,  # Trigger if pain >= 7
                metadata={"trigger_type": "threshold", "threshold_value": 7, "threshold_operator": ">="}
            ),
            CheckinQuestion(
                question_id="base_006",
                question_text="Are you taking all your medications as prescribed?",
                question_type=QuestionType.YES_NO,
                condition_tag="base",
            ),
            
            # === DIABETES-SPECIFIC QUESTIONS ===
            CheckinQuestion(
                question_id="diabetes_001",
                question_text="Have you been monitoring your blood sugar levels?",
                question_type=QuestionType.YES_NO,
                condition_tag="diabetes",
            ),
            CheckinQuestion(
                question_id="diabetes_002",
                question_text="How have your blood sugar readings been? (Normal, Higher than usual, Lower than usual)",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=["Normal/In range", "Higher than usual", "Lower than usual", "Haven't checked"],
                condition_tag="diabetes",
            ),
            CheckinQuestion(
                question_id="diabetes_003",
                question_text="Have you experienced any hypoglycemic episodes (low blood sugar) recently?",
                question_type=QuestionType.YES_NO,
                condition_tag="diabetes",
            ),
            CheckinQuestion(
                question_id="diabetes_004_detail",
                question_text="How many low blood sugar episodes in the past week?",
                question_type=QuestionType.TEXT,
                condition_tag="diabetes",
                depends_on_question_id="diabetes_003",
                depends_on_response=True,
            ),
            
            # === HYPERTENSION-SPECIFIC QUESTIONS ===
            CheckinQuestion(
                question_id="hypertension_001",
                question_text="Have you been checking your blood pressure regularly?",
                question_type=QuestionType.YES_NO,
                condition_tag="hypertension",
            ),
            CheckinQuestion(
                question_id="hypertension_002",
                question_text="How have your blood pressure readings been?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=["Controlled/At goal", "Consistently elevated", "Variable"],
                condition_tag="hypertension",
            ),
            CheckinQuestion(
                question_id="hypertension_003",
                question_text="Have you experienced any dizziness, headaches, or shortness of breath?",
                question_type=QuestionType.YES_NO,
                condition_tag="hypertension",
            ),
            
            # === CARDIAC QUESTIONS ===
            CheckinQuestion(
                question_id="cardiac_001",
                question_text="Have you experienced chest pain, pressure, or tightness?",
                question_type=QuestionType.YES_NO,
                condition_tag="cardiac",
            ),
            CheckinQuestion(
                question_id="cardiac_002_detail",
                question_text="Describe the chest sensation (location, duration, what makes it better/worse):",
                question_type=QuestionType.TEXT,
                condition_tag="cardiac",
                depends_on_question_id="cardiac_001",
                depends_on_response=True,
            ),
            CheckinQuestion(
                question_id="cardiac_003",
                question_text="Have you noticed unusual shortness of breath or fatigue?",
                question_type=QuestionType.YES_NO,
                condition_tag="cardiac",
            ),
            
            # === RESPIRATORY QUESTIONS ===
            CheckinQuestion(
                question_id="respiratory_001",
                question_text="Have you experienced any cough or breathing difficulties?",
                question_type=QuestionType.YES_NO,
                condition_tag="respiratory",
            ),
            CheckinQuestion(
                question_id="respiratory_002_detail",
                question_text="Describe your cough/breathing difficulty (dry/wet, duration, time of day):",
                question_type=QuestionType.TEXT,
                condition_tag="respiratory",
                depends_on_question_id="respiratory_001",
                depends_on_response=True,
            ),
        ]
        
        return questions
    
    def get_question(self, question_id: str) -> Optional[CheckinQuestion]:
        """Retrieve a single question by ID"""
        return next((q for q in self.questions if q.question_id == question_id), None)
    
    def get_questions_by_condition(self, condition_tag: str) -> list[CheckinQuestion]:
        """Get all questions for a specific condition"""
        return [q for q in self.questions if q.condition_tag == condition_tag]


class StaticQuestionnaireGenerator(QuestionnaireGenerator):
    """Generates adaptive questionnaires from a hardcoded question bank with branching logic."""
    
    def __init__(self):
        self.question_bank = QuestionBank()
    
    def generate_questionnaire(self, patient: PatientProfile) -> list[CheckinQuestion]:
        """
        Generate a personalized questionnaire for a patient.
        
        Rules:
        1. Always include base questions (4-6 base questions)
        2. Add condition-specific questions based on patient's conditions
        3. Each question set should be 4-12 questions total
        4. Branching questions are included but only shown when conditions are met
        """
        
        # Start with base questions
        selected_questions = self.question_bank.get_questions_by_condition("base")
        
        # Add condition-specific questions (deduplicate by tag)
        seen_tags = set()
        for condition in patient.conditions:
            condition_tag = self._normalize_condition_tag(condition.condition_name)
            if condition_tag not in seen_tags:
                seen_tags.add(condition_tag)
                condition_questions = self.question_bank.get_questions_by_condition(condition_tag)
                selected_questions.extend(condition_questions)
        
        # Ensure total is within 4-12 range (not counting branching questions yet)
        base_count = len(self.question_bank.get_questions_by_condition("base"))
        if len(selected_questions) > 12:
            # Keep base + highest priority conditions
            selected_questions = self._prioritize_questions(selected_questions, patient)
        elif len(selected_questions) < 4:
            # Shouldn't happen with base questions, but keep as safety
            selected_questions = selected_questions[:4]
        
        return selected_questions
    
    def get_next_question(
        self,
        patient: PatientProfile,
        all_available_questions: list[CheckinQuestion],
        responses_so_far: list[CheckinResponse],
        current_index: int
    ) -> tuple[Optional[CheckinQuestion], int, Optional[str]]:
        """
        Get the next question, applying adaptive branching logic.
        
        Returns (question, actual_index, reasoning) where reasoning is always
        None for the static generator.
        """
        
        if current_index >= len(all_available_questions):
            return None, current_index, None
        
        next_question = all_available_questions[current_index]
        
        # Check if this question has dependencies that aren't met
        if next_question.depends_on_question_id:
            if not self._check_dependency(next_question, responses_so_far):
                # Skip this question and move to next
                return self.get_next_question(
                    patient,
                    all_available_questions,
                    responses_so_far,
                    current_index + 1
                )
        
        return next_question, current_index, None
    
    def _check_dependency(
        self,
        question: CheckinQuestion,
        responses: list[CheckinResponse]
    ) -> bool:
        """Check if a question's dependencies are satisfied"""
        
        if not question.depends_on_question_id:
            return True
        
        # Find the response to the dependency question
        response = next(
            (r for r in responses if r.question_id == question.depends_on_question_id),
            None
        )
        
        if not response:
            return False
        
        # Check if response matches the trigger condition
        if question.depends_on_response is None:
            return True
        
        # For threshold-based triggers (pain >= 7)
        if isinstance(question.depends_on_response, (int, float)):
            metadata = question.metadata
            if metadata.get("trigger_type") == "threshold":
                threshold = metadata.get("threshold_value", question.depends_on_response)
                operator = metadata.get("threshold_operator", ">=")
                
                response_val = response.response_value
                if operator == ">=":
                    return response_val >= threshold
                elif operator == ">":
                    return response_val > threshold
                elif operator == "<=":
                    return response_val <= threshold
                elif operator == "<":
                    return response_val < threshold
                elif operator == "==":
                    return response_val == threshold
        
        # For exact match (yes/no or multiple choice)
        return response.response_value == question.depends_on_response
    
    def _normalize_condition_tag(self, condition_name: str) -> str:
        """Normalize condition name to question bank tag"""
        
        condition_lower = condition_name.lower()
        
        # Map common condition names to tags
        condition_mappings = {
            "diabetes": "diabetes",
            "type 2 diabetes": "diabetes",
            "type 2 diabetes mellitus": "diabetes",
            "hypertension": "hypertension",
            "high blood pressure": "hypertension",
            "cardiac": "cardiac",
            "heart disease": "cardiac",
            "coronary artery disease": "cardiac",
            "cad": "cardiac",
            "respiratory": "respiratory",
            "asthma": "respiratory",
            "copd": "respiratory",
            "chronic obstructive pulmonary disease": "respiratory",
        }
        
        for key, tag in condition_mappings.items():
            if key in condition_lower:
                return tag
        
        # Fallback: use first word
        return condition_lower.split()[0]
    
    def _prioritize_questions(
        self,
        questions: list[CheckinQuestion],
        patient: PatientProfile
    ) -> list[CheckinQuestion]:
        """Prioritize questions when count exceeds 12"""
        
        # Keep all base questions + top 2-3 condition-specific
        base_qs = [q for q in questions if q.condition_tag == "base"]
        condition_qs = [q for q in questions if q.condition_tag != "base"]
        
        # Keep up to 12 total
        max_condition = 12 - len(base_qs)
        return base_qs + condition_qs[:max_condition]


# Backward-compatible alias
AdaptiveQuestionnaireGenerator = StaticQuestionnaireGenerator


# ============================================================================
# LLM-Powered Implementation
# ============================================================================

GENERATION_SYSTEM_PROMPT = """\
You are a clinical pre-visit questionnaire designer. Given a patient's medical \
profile (conditions, medications, demographics), generate a personalized \
check-in questionnaire of 4-12 questions.

Rules:
- Always start with 2-3 general health questions (overall health rating, new \
symptoms, pain level).
- Add condition-specific questions tailored to the patient's actual conditions \
and medications. Be specific -- reference their conditions and drugs by name.
- Use a mix of question types: yes_no, scale_1_10, multiple_choice, text.
- For multiple_choice, include 3-5 options in the "options" array.
- Assign each question a short condition_tag (e.g. "general", "diabetes", \
"hypertension", or whatever fits their conditions).
- Assign sequential question_id values like "q_001", "q_002", etc.
- For each question, include a brief "rationale" explaining why you are asking \
this specific question for this specific patient.

Respond with a JSON object: {"questions": [...]} where each question has:
  question_id, question_text, question_type, condition_tag, rationale
  and optionally: options (for multiple_choice only)

Valid question_type values: yes_no, scale_1_10, multiple_choice, text\
"""

NEXT_QUESTION_SYSTEM_PROMPT = """\
You are an adaptive clinical interviewer conducting a pre-visit check-in. \
Given the patient profile, the questions already answered (with responses), \
and the remaining planned questions, decide what to ask next.

You may:
(a) Pick the next planned question if it is still relevant.
(b) Skip a planned question that is no longer relevant given prior answers.
(c) Generate a NEW follow-up question based on a concerning or noteworthy \
response (e.g., patient reports high pain, new symptoms, missed medications).
(d) End the questionnaire if enough information has been gathered.

Respond with a JSON object:
{
  "action": "ask" | "end",
  "reasoning": "<2-3 sentence clinical reasoning for your decision>",
  "question": {<question object if action is "ask", omit if "end">}
}

The question object must have: question_id, question_text, question_type, \
condition_tag, rationale. Optionally: options (for multiple_choice).

Valid question_type values: yes_no, scale_1_10, multiple_choice, text\
"""


def _build_patient_description(patient: PatientProfile) -> str:
    """Build a text description of the patient for LLM prompts."""
    parts = [f"Patient: {patient.name} (ID: {patient.patient_id})"]
    if patient.conditions:
        conds = ", ".join(
            f"{c.condition_name} ({c.status})" for c in patient.conditions
        )
        parts.append(f"Conditions: {conds}")
    else:
        parts.append("Conditions: None on record")
    if patient.current_medications:
        parts.append(f"Medications: {', '.join(patient.current_medications)}")
    else:
        parts.append("Medications: None on record")
    return "\n".join(parts)


def _parse_question(raw: dict) -> CheckinQuestion:
    """Parse a dict from LLM JSON into a CheckinQuestion."""
    qtype = raw.get("question_type", "text")
    if qtype not in {e.value for e in QuestionType}:
        qtype = "text"
    return CheckinQuestion(
        question_id=raw.get("question_id", "q_000"),
        question_text=raw.get("question_text", ""),
        question_type=QuestionType(qtype),
        condition_tag=raw.get("condition_tag", "general"),
        options=raw.get("options"),
        rationale=raw.get("rationale"),
    )




class LLMQuestionnaireGenerator(QuestionnaireGenerator):
    """Generates adaptive questionnaires using an LLM."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def generate_questionnaire(self, patient: PatientProfile, model: str | None = None) -> list[CheckinQuestion]:
        messages = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": _build_patient_description(patient)},
        ]

        logger.info("[GENERATE] Provider=%s  Model=%s", self.provider.name, model or self.provider.default_model)
        logger.info("[GENERATE] System prompt (first 200 chars): %.200s", messages[0]["content"])
        logger.info("[GENERATE] User prompt:\n%s", messages[1]["content"])

        content = self.provider.chat_completion(messages, json_mode=True, model=model)
        logger.info("[GENERATE] Raw LLM response:\n%s", content)

        try:
            data = json.loads(content)
            raw_questions = data.get("questions", data if isinstance(data, list) else [])
            questions = [_parse_question(q) for q in raw_questions]
            if not questions:
                raise ValueError("Empty question list from LLM")
            logger.info("[GENERATE] Parsed %d questions:", len(questions))
            for i, q in enumerate(questions):
                logger.info("  [%d] %s (%s) - %s", i, q.question_id, q.question_type.value, q.question_text)
            return questions
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Failed to parse LLM response (%s), retrying once", exc)
            # Retry with correction
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": "That was not valid JSON. Please respond with ONLY a JSON object: {\"questions\": [...]}",
            })
            content2 = self.provider.chat_completion(messages, json_mode=True, model=model)
            if content2:
                try:
                    data2 = json.loads(content2)
                    raw2 = data2.get("questions", data2 if isinstance(data2, list) else [])
                    questions2 = [_parse_question(q) for q in raw2]
                    if questions2:
                        return questions2
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            logger.warning("LLM retry also failed, using fallback questions")
            raise ValueError("LLM failed to generate valid questions after retry")

    def get_next_question(
        self,
        patient: PatientProfile,
        all_available_questions: list[CheckinQuestion],
        responses_so_far: list[CheckinResponse],
        current_index: int,
        model: str | None = None,
    ) -> tuple[Optional[CheckinQuestion], int, Optional[str]]:
        if current_index >= len(all_available_questions):
            return None, current_index, None

        # For the first question (no responses yet), just return the planned
        # question directly -- no LLM call needed since we just generated the plan.
        if not responses_so_far:
            q = all_available_questions[current_index]
            return q, current_index, q.rationale

        # Build conversation context for the LLM
        answered_text = ""
        for resp in responses_so_far:
            q = next((q for q in all_available_questions if q.question_id == resp.question_id), None)
            q_text = q.question_text if q else resp.question_id
            answered_text += f"  Q: {q_text}\n  A: {resp.response_value}\n\n"

        remaining = all_available_questions[current_index:]
        remaining_text = "\n".join(
            f"  - [{i + current_index}] [{q.condition_tag}] {q.question_id}: {q.question_text}"
            for i, q in enumerate(remaining)
        )

        user_msg = (
            f"{_build_patient_description(patient)}\n\n"
            f"Questions answered so far ({len(responses_so_far)}):\n{answered_text}\n\n"
            f"Remaining planned questions ({len(remaining)}):\n{remaining_text}\n\n"
            f"What should be the next question? You MUST use one of the remaining "
            f"planned question_ids above, or set action to 'end' if done."
        )

        messages = [
            {"role": "system", "content": NEXT_QUESTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        logger.info("[NEXT_Q] Provider=%s  Model=%s  responses=%d  remaining=%d",
                    self.provider.name, model or self.provider.default_model,
                    len(responses_so_far), len(remaining))
        logger.info("[NEXT_Q] User prompt:\n%s", user_msg)

        content = self.provider.chat_completion(messages, json_mode=True, model=model)
        logger.info("[NEXT_Q] Raw LLM response:\n%s", content)

        try:
            data = json.loads(content)
            reasoning = data.get("reasoning", "")
            action = data.get("action", "ask")

            logger.info("[NEXT_Q] Action=%s  Reasoning=%s", action, reasoning)

            if action == "end":
                logger.info("[NEXT_Q] LLM decided to END questionnaire")
                return None, current_index, reasoning

            raw_q = data.get("question")
            if not raw_q:
                logger.info("[NEXT_Q] No question in response, using planned index %d", current_index)
                return all_available_questions[current_index], current_index, reasoning

            question = _parse_question(raw_q)
            question.rationale = question.rationale or reasoning
            logger.info("[NEXT_Q] LLM chose: %s - %s", question.question_id, question.question_text)

            # Try to match by question_id first
            for i in range(current_index, len(all_available_questions)):
                if all_available_questions[i].question_id == question.question_id:
                    # Use the planned question object but attach LLM reasoning
                    planned = all_available_questions[i]
                    planned.rationale = question.rationale or reasoning
                    return planned, i, reasoning

            # If LLM returned an unrecognized ID, try matching by question text
            q_text_lower = question.question_text.lower().strip()
            for i in range(current_index, len(all_available_questions)):
                if all_available_questions[i].question_text.lower().strip() == q_text_lower:
                    planned = all_available_questions[i]
                    planned.rationale = question.rationale or reasoning
                    return planned, i, reasoning

            # Truly new follow-up question -- insert right after current_index
            # so we don't skip remaining planned questions
            all_available_questions.insert(current_index, question)
            return question, current_index, reasoning

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ValueError(f"Failed to parse LLM next-question response: {exc}")
