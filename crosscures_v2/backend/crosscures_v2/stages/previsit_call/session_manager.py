"""Pre-visit call — Maria-led structured intake interview."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from crosscures_v2.db_models import PrevisitSessionDB, PrevisitCallSlotDB
from crosscures_v2.agent.llm import call_llm, LLMUnavailableError
from crosscures_v2.agent.context import assemble_context
from crosscures_v2.agent.validator import validate_response
from crosscures_v2.memory.writer import write_episodic_memory


MARIA_FIRST_MESSAGE = (
    "Hey there, I'm Maria from CrossCures. "
    "Today we'll be conducting a pre-visit consultation. "
    "Are you ready to get started?"
)

PREVISIT_SYSTEM_PROMPT = """You are Maria. A calm, perceptive, and highly attentive female virtual assistant modeled after a compassionate physician.

Your approach is warm, professional, and grounded – like a trusted healthcare provider during an initial consultation.
You're naturally empathetic and observant, asking thoughtful follow-up questions that show you're truly listening and committed to understanding the full context of the patient's health concerns.
You are gentle but thorough, able to guide patients through potentially sensitive conversations with ease and kindness.
You speak clearly and confidently, with a reassuring tone that inspires trust and makes patients feel safe, respected, and well cared for.
You stay calm and focused no matter the situation – never rushing, never cold.
You have excellent conversational skills – human, reassuring, and medical-grade competence.

STRICT FORMATTING RULES — follow these without exception:
- Write in plain, natural spoken English only — as if talking to someone face to face
- Never use markdown: no headers, no bullet points, no bold, no italics, no horizontal rules, no code blocks
- Never use emojis or special symbols
- Keep every response to 2 to 4 sentences maximum unless the patient explicitly asks for more detail
- Never ask more than one question in a response
- Be warm, direct, and conversational

ENVIRONMENT:
You are conducting a voice-based pre-visit consultation with a patient who has booked an appointment. You are speaking directly to the patient via a voice-enabled interface, typically within 24 to 72 hours before their scheduled appointment.

GOAL — gather all essential health details before the visit including:
- Chief complaint and reason for the visit
- Description and timeline of current symptoms
- Past medical history (illnesses, surgeries, hospitalizations)
- Current medications and known allergies
- Any relevant family history or lifestyle factors

Use open-ended follow-ups such as "Can you tell me more about when that started?" or "And how would you describe the pain — sharp, dull, throbbing?" Regularly check in and give the patient a sense of progress with affirmations like "Okay, that's really helpful, thank you" or "We're almost done — just a few more questions."

WRAP-UP:
Once you have gathered all details, briefly recap what you heard and ask: "Did I capture that correctly, or is there anything I missed?" Wait for the patient to confirm or correct before closing.

CLOSING:
After the patient confirms the summary is accurate, say exactly: "Great — thanks for confirming. I'll share this information with your doctor so they're fully prepared for your visit. If they need to speak with you sooner, they'll reach out directly; otherwise, you're all set. We look forward to seeing you. Have a lovely rest of your day."

GUARDRAILS:
- Never make diagnostic conclusions or recommend medication changes
- If the patient reports a serious or urgent symptom such as chest pain or trouble breathing, say: "That could be serious. I recommend you contact emergency services or go to the nearest emergency room immediately."
- Never mention that you are an AI unless explicitly asked
- Mirror the patient's tone and energy
- Do not conclude until the patient clearly confirms the summary is correct"""


def start_session(
    patient_id: str,
    db: Session,
    slot_id: Optional[str] = None,
    appointment_id: Optional[str] = None,
) -> dict:
    session = PrevisitSessionDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        slot_id=slot_id,
        appointment_id=appointment_id,
        started_at=datetime.utcnow(),
        turns=[{
            "turn_id": str(uuid.uuid4()),
            "speaker": "agent",
            "content": MARIA_FIRST_MESSAGE,
            "timestamp": datetime.utcnow().isoformat(),
        }],
        status="active",
    )
    db.add(session)

    # Mark the slot as in-progress if provided
    if slot_id:
        slot = db.query(PrevisitCallSlotDB).filter(
            PrevisitCallSlotDB.id == slot_id,
            PrevisitCallSlotDB.patient_id == patient_id,
        ).first()
        if slot:
            slot.session_id = session.id
            slot.status = "in_progress"

    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "initial_message": MARIA_FIRST_MESSAGE,
        "status": session.status,
    }


def process_turn(session_id: str, patient_id: str, content: str, db: Session) -> dict:
    session = db.query(PrevisitSessionDB).filter(
        PrevisitSessionDB.id == session_id,
        PrevisitSessionDB.patient_id == patient_id,
        PrevisitSessionDB.status == "active",
    ).first()

    if not session:
        return {"error": "Session not found or not active"}

    ctx = assemble_context(patient_id, db, query=content)
    context_block = f"""Patient Health Context:
{ctx['patient_summary']}

Recent Symptoms (last 14 days):
{ctx['symptom_trend']}

Memory Highlights:
{ctx['memory_highlights']}"""

    messages = []
    turns = session.turns or []
    for turn in turns[-10:]:
        if turn.get("speaker") == "patient":
            messages.append({"role": "user", "content": turn["content"]})
        elif turn.get("speaker") == "agent":
            messages.append({"role": "assistant", "content": turn["content"]})

    messages.append({
        "role": "user",
        "content": f"{context_block}\n\nPatient says: {content}",
    })

    turn_id = str(uuid.uuid4())

    try:
        llm_resp = call_llm(
            system_prompt=PREVISIT_SYSTEM_PROMPT,
            messages=messages,
            patient_id=patient_id,
            purpose="previsit_turn",
            db=db,
            max_tokens=512,
        )
        validation = validate_response(llm_resp.content)
        agent_content = validation.sanitized_output
    except (LLMUnavailableError, Exception):
        agent_content = "I'm having a little trouble right now. Could you give me just a moment? Thank you for your patience."

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
    session = db.query(PrevisitSessionDB).filter(
        PrevisitSessionDB.id == session_id,
        PrevisitSessionDB.patient_id == patient_id,
    ).first()

    if not session:
        return {"error": "Session not found"}

    session.status = "completed"
    session.ended_at = datetime.utcnow()

    turns = session.turns or []
    patient_utterances = [t["content"] for t in turns if t.get("speaker") == "patient"]

    summary = {
        "session_id": session_id,
        "duration_minutes": round(
            (datetime.utcnow() - session.started_at).total_seconds() / 60, 1
        ),
        "patient_turn_count": len(patient_utterances),
        "generated_at": datetime.utcnow().isoformat(),
    }
    session.summary = summary

    # Mark slot as completed
    if session.slot_id:
        slot = db.query(PrevisitCallSlotDB).filter(
            PrevisitCallSlotDB.id == session.slot_id
        ).first()
        if slot:
            slot.status = "completed"

    db.commit()

    # Write to episodic memory
    memory_content = (
        f"Pre-visit call on {datetime.utcnow().date()}. "
        f"{len(patient_utterances)} patient responses recorded."
    )
    write_episodic_memory(
        patient_id, session_id, memory_content, ["previsit_call"], db
    )

    return summary


def schedule_slot(
    patient_id: str,
    scheduled_at: datetime,
    db: Session,
    appointment_id: Optional[str] = None,
) -> dict:
    slot = PrevisitCallSlotDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        appointment_id=appointment_id,
        scheduled_at=scheduled_at,
        duration_minutes=15,
        status="scheduled",
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {
        "slot_id": slot.id,
        "scheduled_at": slot.scheduled_at.isoformat(),
        "duration_minutes": slot.duration_minutes,
        "status": slot.status,
    }


def list_slots(patient_id: str, db: Session) -> list:
    slots = (
        db.query(PrevisitCallSlotDB)
        .filter(PrevisitCallSlotDB.patient_id == patient_id)
        .order_by(PrevisitCallSlotDB.scheduled_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "slot_id": s.id,
            "appointment_id": s.appointment_id,
            "scheduled_at": s.scheduled_at.isoformat(),
            "duration_minutes": s.duration_minutes,
            "status": s.status,
            "session_id": s.session_id,
        }
        for s in slots
    ]
