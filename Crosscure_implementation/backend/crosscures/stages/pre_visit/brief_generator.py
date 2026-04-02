"""Pre-visit brief generator — creates physician briefs 72h before appointment."""
import uuid
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ...db_models import AppointmentDB, PhysicianBriefDB, SymptomLogDB, HealthRecordDB, WearableSampleDB, PrescriptionDB
from ...consent.models import ConsentAction
from ...consent.store import ConsentStore
from ...agent.llm import call_llm, LLMUnavailableError
from ...agent.context import assemble_context
from ...events import bus as event_bus
from ...events.models import EventType, EventSource


BRIEF_SYSTEM_PROMPT = """You are CrossCures, a clinical AI assistant. Generate a concise, structured pre-visit physician brief based on the patient data provided. 

Output ONLY valid JSON with this exact structure:
{
  "patient_snapshot": "3-5 bullet points about chronic conditions, active medications, known allergies",
  "symptom_trends": "14-day symptom trajectory, notable changes — narrative plus any notable patterns",
  "wearable_highlights": "HRV, sleep, SpO2 anomalies if available, otherwise null",
  "medication_adherence": "Adherence rate per medication as reported by patient",
  "patient_concerns": "Verbatim high-priority patient-reported concerns",
  "suggested_discussion_points": ["Point 1", "Point 2", "Point 3"]
}

Rules:
- Do NOT make diagnostic conclusions
- Do NOT recommend dose changes
- All claims must be traceable to the provided data
- Use plain clinical English
- If data is missing for a section, say "No data available for this period"
"""


def generate_brief(patient_id: str, appointment_id: str, db: Session) -> dict:
    """Generate a pre-visit physician brief."""
    consent_store = ConsentStore(db)
    consent_store.require(patient_id, ConsentAction.PHYSICIAN_BRIEF_SHARING)
    consent_store.require(patient_id, ConsentAction.LLM_INFERENCE)

    # Check for existing brief
    appointment = db.query(AppointmentDB).filter(
        AppointmentDB.id == appointment_id,
        AppointmentDB.patient_id == patient_id,
    ).first()

    if appointment and appointment.brief_generated:
        existing = db.query(PhysicianBriefDB).filter(
            PhysicianBriefDB.appointment_id == appointment_id
        ).first()
        if existing:
            return _brief_to_dict(existing)

    # Assemble context
    ctx = assemble_context(patient_id, db)

    # Get recent symptom logs
    since_14d = datetime.utcnow() - timedelta(days=14)
    symptom_logs = db.query(SymptomLogDB).filter(
        SymptomLogDB.patient_id == patient_id,
        SymptomLogDB.submitted_at >= since_14d,
    ).order_by(SymptomLogDB.session_date.desc()).all()

    symptom_summary = "No check-ins in the last 14 days."
    if symptom_logs:
        log_summaries = []
        for log in symptom_logs:
            responses_text = []
            for resp in (log.responses or []):
                if resp.get("value") is not None:
                    responses_text.append(f"{resp.get('question_id')}: {resp.get('value')}")
            if responses_text:
                log_summaries.append(f"[{log.session_date}] " + "; ".join(responses_text[:4]))
        symptom_summary = "\n".join(log_summaries)

    user_message = f"""Patient context:
{ctx['patient_summary']}

Symptom logs (last 14 days):
{symptom_summary}

Wearable data:
{ctx['wearable_summary']}

Active prescriptions:
{json.dumps(ctx['prescriptions'], indent=2)}

Memory highlights:
{ctx['memory_highlights']}

Generate the pre-visit brief as structured JSON."""

    try:
        llm_resp = call_llm(
            system_prompt=BRIEF_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            patient_id=patient_id,
            purpose="pre_visit_brief",
            db=db,
            max_tokens=2000,
        )

        # Parse the JSON sections
        try:
            sections = json.loads(llm_resp.content)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            match = re.search(r'\{.*\}', llm_resp.content, re.DOTALL)
            sections = json.loads(match.group()) if match else {}
    except LLMUnavailableError as e:
        sections = {
            "patient_snapshot": ctx["patient_summary"],
            "symptom_trends": symptom_summary,
            "wearable_highlights": ctx["wearable_summary"],
            "medication_adherence": "Unable to generate — LLM unavailable",
            "patient_concerns": "Unable to generate — LLM unavailable",
            "suggested_discussion_points": ["Review recent symptom logs", "Check medication adherence"],
        }

    brief = PhysicianBriefDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        appointment_id=appointment_id,
        generated_at=datetime.utcnow(),
        sections=sections,
        citations=[],
        delivery_status="queued",
    )
    db.add(brief)

    if appointment:
        appointment.brief_generated = True
        appointment.brief_id = brief.id

    db.commit()
    db.refresh(brief)

    event_bus.emit(
        event_bus.make_event(
            EventType.BRIEF_GENERATED,
            patient_id=patient_id,
            source=EventSource.AGENT,
            payload={"brief_id": brief.id, "appointment_id": appointment_id},
        ),
        db,
    )

    return _brief_to_dict(brief)


def _brief_to_dict(brief: PhysicianBriefDB) -> dict:
    return {
        "brief_id": brief.id,
        "patient_id": brief.patient_id,
        "appointment_id": brief.appointment_id,
        "generated_at": brief.generated_at.isoformat(),
        "sections": brief.sections,
        "citations": brief.citations or [],
        "delivery_status": brief.delivery_status,
    }
