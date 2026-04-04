"""Clinic companion — stage 2 session management."""
import uuid
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from crosscures_v2.db_models import ClinicSessionDB
from crosscures_v2.consent.models import ConsentAction
from crosscures_v2.consent.store import ConsentStore
from crosscures_v2.agent.llm import call_llm, LLMUnavailableError
from crosscures_v2.agent.context import assemble_context
from crosscures_v2.agent.validator import validate_response
from crosscures_v2.events import bus as event_bus
from crosscures_v2.events.models import EventType, EventSource
from crosscures_v2.memory.writer import write_episodic_memory


CLINIC_SYSTEM_PROMPT = """You are Maria, an AI clinic companion built into the CrossCures health app.

STRICT FORMATTING RULES — follow these without exception:
- Write in plain, natural spoken English only — as if talking to someone face to face
- Never use markdown: no headers, no bullet points, no bold, no italics, no horizontal rules, no code blocks
- Never use emojis or special symbols
- Keep every response to 2 to 4 sentences maximum unless the patient explicitly asks for more detail
- Be warm, direct, and conversational

Your role:
- Help the patient recall their health history, medications, and recent symptoms
- Help them formulate questions for the doctor in plain language
- Provide relevant context from their medical records naturally in conversation

When citing records, say it naturally — for example: "According to your records, you are currently taking Metformin and Lisinopril."
Never make diagnostic conclusions or recommend medication changes.
If something is not in their records, say so simply and move on.

Context from the patient's records will be provided with each turn."""


def start_session(patient_id: str, db: Session, appointment_id: Optional[str] = None, audio_enabled: bool = False) -> dict:
    consent_store = ConsentStore(db)
    consent_store.require(patient_id, ConsentAction.LLM_INFERENCE)
    if audio_enabled:
        consent_store.require(patient_id, ConsentAction.AMBIENT_LISTENING)

    session = ClinicSessionDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        appointment_id=appointment_id,
        started_at=datetime.utcnow(),
        audio_enabled=audio_enabled,
        turns=[],
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    event_bus.emit(
        event_bus.make_event(
            EventType.CLINIC_SESSION_STARTED,
            patient_id=patient_id,
            source=EventSource.WEB,
            payload={"session_id": session.id},
        ),
        db,
    )

    return _session_to_dict(session)


def process_turn(session_id: str, patient_id: str, content: str, db: Session) -> dict:
    session = db.query(ClinicSessionDB).filter(
        ClinicSessionDB.id == session_id,
        ClinicSessionDB.patient_id == patient_id,
        ClinicSessionDB.status == "active",
    ).first()

    if not session:
        return {"error": "Session not found or not active"}

    ctx = assemble_context(patient_id, db, query=content)

    context_block = f"""Patient Health Context:
{ctx['patient_summary']}

Recent Symptoms (last 14 days):
{ctx['symptom_trend']}

Wearable Data:
{ctx['wearable_summary']}

Memory Highlights:
{ctx['memory_highlights']}"""

    # Build conversation history from turns
    messages = []
    turns = session.turns or []
    for turn in turns[-6:]:  # last 3 exchanges
        if turn.get("speaker") == "patient":
            messages.append({"role": "user", "content": turn["content"]})
        elif turn.get("speaker") == "agent":
            messages.append({"role": "assistant", "content": turn["content"]})

    messages.append({"role": "user", "content": f"{context_block}\n\nPatient says: {content}"})

    turn_id = str(uuid.uuid4())

    try:
        llm_resp = call_llm(
            system_prompt=CLINIC_SYSTEM_PROMPT,
            messages=messages,
            patient_id=patient_id,
            purpose="clinic_turn",
            db=db,
            max_tokens=1024,
        )
        validation = validate_response(llm_resp.content)
        agent_content = validation.sanitized_output
    except (LLMUnavailableError, Exception):
        agent_content = "I'm temporarily unable to access AI assistance. Please discuss your concerns directly with your physician. Your health records are available in the app for reference."

    # Update session turns
    new_turns = list(turns)
    new_turns.append({
        "turn_id": turn_id,
        "speaker": "patient",
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    new_turns.append({
        "turn_id": str(uuid.uuid4()),
        "speaker": "agent",
        "content": agent_content,
        "timestamp": datetime.utcnow().isoformat(),
    })

    session.turns = new_turns
    db.commit()

    return {
        "turn_id": turn_id,
        "content": agent_content,
        "session_id": session_id,
    }


def end_session(session_id: str, patient_id: str, db: Session) -> dict:
    session = db.query(ClinicSessionDB).filter(
        ClinicSessionDB.id == session_id,
        ClinicSessionDB.patient_id == patient_id,
    ).first()

    if not session:
        return {"error": "Session not found"}

    session.status = "ended"
    session.ended_at = datetime.utcnow()

    # Generate summary
    turns = session.turns or []
    patient_utterances = [t["content"] for t in turns if t.get("speaker") == "patient"]
    agent_responses = [t["content"] for t in turns if t.get("speaker") == "agent"]

    summary = {
        "session_id": session_id,
        "duration_minutes": round((datetime.utcnow() - session.started_at).total_seconds() / 60, 1),
        "turn_count": len([t for t in turns if t.get("speaker") == "patient"]),
        "key_topics": _extract_topics(patient_utterances),
        "generated_at": datetime.utcnow().isoformat(),
    }
    session.summary = summary
    db.commit()

    # Write to episodic memory
    memory_content = f"Clinic session on {datetime.utcnow().date()}. Topics: {', '.join(summary['key_topics'][:5])}. {len(patient_utterances)} exchanges."
    write_episodic_memory(patient_id, session_id, memory_content, ["clinic_session"], db)

    event_bus.emit(
        event_bus.make_event(
            EventType.CLINIC_SESSION_ENDED,
            patient_id=patient_id,
            source=EventSource.WEB,
            payload={"session_id": session_id},
        ),
        db,
    )

    return summary


def _extract_topics(utterances: list) -> list:
    """Simple keyword extraction for session topics."""
    keywords = set()
    topic_words = ["pain", "medication", "sleep", "fatigue", "breathing", "heart", "blood", "pressure", "anxiety", "mood", "exercise", "diet"]
    for utterance in utterances:
        lower = utterance.lower()
        for word in topic_words:
            if word in lower:
                keywords.add(word)
    return list(keywords)[:8]


def _session_to_dict(session: ClinicSessionDB) -> dict:
    return {
        "session_id": session.id,
        "patient_id": session.patient_id,
        "appointment_id": session.appointment_id,
        "started_at": session.started_at.isoformat(),
        "audio_enabled": session.audio_enabled,
        "status": session.status,
        "turns": session.turns or [],
    }
