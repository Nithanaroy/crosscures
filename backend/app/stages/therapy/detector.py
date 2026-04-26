"""Outcome deviation detector for Stage 3 — Therapy Guardian."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.db_models import PrescriptionDB, PhysicianAlertDB
from app.consent.models import ConsentAction
from app.consent.store import ConsentStore
from app.agent.llm import call_llm, LLMUnavailableError
from app.agent.context import assemble_context
from app.events import bus as event_bus
from app.events.models import EventType, EventSource


RED_FLAG_SIDE_EFFECTS = {
    "chest pain", "severe chest pain", "difficulty breathing", "shortness of breath",
    "severe allergic reaction", "anaphylaxis", "muscle weakness", "rhabdomyolysis",
    "severe bleeding", "vision loss", "stroke symptoms", "heart palpitations",
    "severe dizziness", "fainting", "seizure",
}


ALERT_SYSTEM_PROMPT = """You are CrossCures Therapy Guardian. Generate a concise physician alert about a therapy outcome deviation.

Output ONLY valid JSON:
{
  "patient_snapshot": "brief patient description with conditions and allergies",
  "prescription_summary": "medication name, dose, start date, prescribing physician",
  "expected_outcome": "what was expected by this point in therapy",
  "observed_outcome": "what the patient actually reported",
  "wearable_evidence": "relevant wearable data if available, otherwise null",
  "deviation_summary": "plain-English summary of the gap between expected and observed",
  "suggested_actions": ["Action 1", "Action 2", "Action 3"]
}

Rules: No diagnostic conclusions. Suggested actions are options, not orders."""


def evaluate_outcomes(patient_id: str, prescription_id: str, checkin_responses: list, day_since_start: int, db: Session) -> dict:
    """Evaluate therapy outcomes and detect deviations."""
    prescription = db.query(PrescriptionDB).filter(
        PrescriptionDB.id == prescription_id,
        PrescriptionDB.patient_id == patient_id,
    ).first()

    if not prescription:
        return {"error": "Prescription not found"}

    criteria_results = []
    missed_criteria = 0
    red_flag_detected = False
    side_effects = []

    # Check for red flag side effects in free text responses
    for resp in checkin_responses:
        val = str(resp.get("value", "")).lower()
        for flag in RED_FLAG_SIDE_EFFECTS:
            if flag in val:
                red_flag_detected = True
                side_effects.append(flag)

    # Evaluate pain criterion (pain score should decrease)
    pain_score = None
    for resp in checkin_responses:
        if "pain" in resp.get("question_id", "").lower():
            try:
                pain_score = float(resp.get("value", 10))
            except (ValueError, TypeError):
                pass

    if pain_score is not None and day_since_start >= 14:
        target = 4.0
        met = pain_score <= target
        if not met:
            missed_criteria += 1
        delta = pain_score - target
        criteria_results.append({
            "criterion_id": "pain_reduction",
            "description": f"Pain level ≤ {target}/10 by day 14",
            "met": met,
            "observed_value": pain_score,
            "expected_value": target,
            "delta": delta,
        })

    # Determine overall status
    if red_flag_detected:
        overall_status = "deviated"
        deviation_severity = "severe"
    elif missed_criteria >= 2:
        overall_status = "deviated"
        deviation_severity = "moderate"
    elif missed_criteria == 1:
        if any(abs(r.get("delta", 0) or 0) > 2 for r in criteria_results if not r["met"]):
            overall_status = "deviating"
            deviation_severity = "moderate"
        else:
            overall_status = "deviating"
            deviation_severity = "mild"
    else:
        overall_status = "on_track"
        deviation_severity = None

    evaluation = {
        "evaluation_id": str(uuid.uuid4()),
        "prescription_id": prescription_id,
        "assessment_day": day_since_start,
        "criteria_results": criteria_results,
        "overall_status": overall_status,
        "deviation_severity": deviation_severity,
        "side_effects": side_effects,
        "red_flag_detected": red_flag_detected,
    }

    # Generate alert if needed
    if overall_status == "deviated" or (deviation_severity and deviation_severity in ("severe", "moderate")):
        _generate_alert(patient_id, prescription, evaluation, db)

    return evaluation


def _generate_alert(patient_id: str, prescription: PrescriptionDB, evaluation: dict, db: Session):
    """Generate a physician alert for the deviation."""
    consent_store = ConsentStore(db)
    try:
        consent_store.require(patient_id, ConsentAction.PHYSICIAN_ALERT_SHARING)
    except Exception:
        return

    ctx = assemble_context(patient_id, db)

    user_msg = f"""Patient context: {ctx['patient_summary']}

Prescription: {prescription.medication_name} {prescription.dose} {prescription.frequency}
Started: {prescription.start_date}
Day of assessment: {evaluation['assessment_day']}

Criteria results: {evaluation['criteria_results']}
Side effects reported: {evaluation.get('side_effects', [])}
Red flag: {evaluation.get('red_flag_detected', False)}

Generate the physician alert as structured JSON."""

    try:
        llm_resp = call_llm(
            system_prompt=ALERT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            patient_id=patient_id,
            purpose="therapy_alert",
            db=db,
            max_tokens=1000,
        )
        import json, re
        try:
            sections = json.loads(llm_resp.content)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', llm_resp.content, re.DOTALL)
            sections = json.loads(match.group()) if match else {}
    except LLMUnavailableError:
        sections = {
            "patient_snapshot": ctx["patient_summary"],
            "prescription_summary": f"{prescription.medication_name} {prescription.dose}",
            "expected_outcome": "Expected improvement per therapy plan",
            "observed_outcome": "Patient reported deviation from expected outcomes",
            "wearable_evidence": None,
            "deviation_summary": "Outcome deviation detected — LLM unavailable for detailed analysis",
            "suggested_actions": ["Review patient's recent check-in responses", "Consider scheduling follow-up"],
        }

    requires_ack = evaluation.get("deviation_severity") == "severe"
    alert = PhysicianAlertDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        prescription_id=prescription.id,
        generated_at=datetime.utcnow(),
        severity=evaluation.get("deviation_severity", "mild"),
        sections=sections,
        citations=[],
        delivery_status="queued",
        requires_acknowledgment=requires_ack,
    )
    db.add(alert)
    db.commit()

    event_bus.emit(
        event_bus.make_event(
            EventType.ALERT_GENERATED,
            patient_id=patient_id,
            source=EventSource.AGENT,
            payload={"alert_id": alert.id, "severity": evaluation.get("deviation_severity")},
        ),
        db,
    )
