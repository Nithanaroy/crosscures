"""Adaptive check-in question generator."""
from datetime import date
from typing import List
from sqlalchemy.orm import Session

from crosscures_v2.db_models import HealthRecordDB


BASE_QUESTIONS = [
    {
        "question_id": "base_pain",
        "text": "On a scale of 1–10, how would you rate your overall pain level today?",
        "response_type": "scale_1_10",
        "domain": "pain",
        "source": "base",
        "parent_question_id": None,
        "condition_trigger": None,
    },
    {
        "question_id": "base_fatigue",
        "text": "How fatigued do you feel today compared to your usual? (1 = not at all, 10 = extremely)",
        "response_type": "scale_1_10",
        "domain": "fatigue",
        "source": "base",
        "parent_question_id": None,
        "condition_trigger": None,
    },
    {
        "question_id": "base_sleep",
        "text": "How many hours of sleep did you get last night?",
        "response_type": "free_text",
        "domain": "sleep",
        "source": "base",
        "parent_question_id": None,
        "condition_trigger": None,
    },
    {
        "question_id": "base_mood",
        "text": "How would you describe your mood today? (1 = very low, 10 = excellent)",
        "response_type": "scale_1_10",
        "domain": "mood",
        "source": "base",
        "parent_question_id": None,
        "condition_trigger": None,
    },
]

PAIN_FOLLOWUP = {
    "question_id": "pain_followup_location",
    "text": "You mentioned significant pain. Where are you experiencing it, and how long has it been present?",
    "response_type": "free_text",
    "domain": "pain",
    "source": "base",
    "parent_question_id": "base_pain",
    "condition_trigger": "response.scale >= 7",
}

CONDITION_QUESTIONS = {
    "diabetes": [
        {
            "question_id": "diabetes_glucose",
            "text": "Have you checked your blood glucose today? If yes, what was the reading (mg/dL)?",
            "response_type": "free_text",
            "domain": "cardiovascular",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
        {
            "question_id": "diabetes_adherence",
            "text": "Did you take your diabetes medication as prescribed today?",
            "response_type": "yes_no",
            "domain": "medication_adherence",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
    ],
    "hypertension": [
        {
            "question_id": "bp_reading",
            "text": "Have you taken your blood pressure today? If yes, what was the reading?",
            "response_type": "free_text",
            "domain": "cardiovascular",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
    ],
    "parkinson": [
        {
            "question_id": "parkinson_tremor",
            "text": "On a scale of 1–10, how severe are your tremors today?",
            "response_type": "scale_1_10",
            "domain": "mobility",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
        {
            "question_id": "parkinson_mobility",
            "text": "How is your mobility and balance today compared to your baseline?",
            "response_type": "free_text",
            "domain": "mobility",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
    ],
    "asthma": [
        {
            "question_id": "asthma_breathing",
            "text": "Have you had any shortness of breath or wheezing in the last 24 hours?",
            "response_type": "yes_no",
            "domain": "cardiovascular",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
    ],
    "depression": [
        {
            "question_id": "depression_phq2_interest",
            "text": "Over the past 2 weeks, how often have you had little interest or pleasure in doing things? (0=not at all, 3=nearly every day)",
            "response_type": "scale_1_10",
            "domain": "mood",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
    ],
    "default": [
        {
            "question_id": "medication_general",
            "text": "Have you taken all your prescribed medications today?",
            "response_type": "yes_no",
            "domain": "medication_adherence",
            "source": "condition_specific",
            "parent_question_id": None,
            "condition_trigger": None,
        },
    ],
}


def generate_checkin(patient_id: str, session_date: date, db: Session) -> List[dict]:
    """Generate adaptive check-in questions for a patient."""
    questions = list(BASE_QUESTIONS)

    # Get patient conditions from health records
    records = db.query(HealthRecordDB).filter(
        HealthRecordDB.patient_id == patient_id,
        HealthRecordDB.resource_type.in_(["Condition", "DiagnosticReport"]),
    ).all()

    condition_keywords = set()
    for record in records:
        display = record.display_text.lower()
        if "diabet" in display:
            condition_keywords.add("diabetes")
        if "hypertens" in display or "blood pressure" in display:
            condition_keywords.add("hypertension")
        if "parkinson" in display:
            condition_keywords.add("parkinson")
        if "asthma" in display:
            condition_keywords.add("asthma")
        if "depress" in display:
            condition_keywords.add("depression")

    # Add condition-specific questions (up to 6)
    condition_q_count = 0
    for condition in condition_keywords:
        if condition_q_count >= 6:
            break
        cqs = CONDITION_QUESTIONS.get(condition, [])
        for q in cqs:
            if condition_q_count >= 6:
                break
            questions.append(q)
            condition_q_count += 1

    # If no condition questions, add default medication adherence
    if condition_q_count == 0 and records:
        questions.append(CONDITION_QUESTIONS["default"][0])

    # Cap at 12 questions
    questions = questions[:12]

    return questions


def inject_followup(questions: List[dict], responses: List[dict]) -> List[dict]:
    """Return follow-up questions based on responses."""
    followups = []
    for resp in responses:
        if resp.get("question_id") == "base_pain":
            try:
                val = int(resp.get("value", 0))
                if val >= 7:
                    followups.append(PAIN_FOLLOWUP)
            except (ValueError, TypeError):
                pass
    return followups
