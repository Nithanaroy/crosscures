"""
Stage 1 MVP - Adaptive Question Generator with Branching Logic (Service Layer)
Business logic for generating personalized questionnaires.
"""
from crosscures.models.schemas import CheckinQuestion, CheckinResponse, PatientProfile, QuestionType
from typing import Optional


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


class AdaptiveQuestionnaireGenerator:
    """Generates adaptive questionnaires based on patient profile"""
    
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
    ) -> tuple[Optional[CheckinQuestion], int]:
        """
        Get the next question, applying adaptive branching logic.
        
        Returns (question, actual_index) so the caller knows which index
        was actually selected (may differ from current_index if questions
        were skipped due to unmet dependencies).
        """
        
        if current_index >= len(all_available_questions):
            return None, current_index
        
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
        
        return next_question, current_index
    
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
