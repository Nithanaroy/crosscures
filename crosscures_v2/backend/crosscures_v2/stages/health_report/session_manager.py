"""Health condition report — Maria transcribes and asks ≤ 3 follow-up questions."""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from crosscures_v2.db_models import HealthReportSessionDB
from crosscures_v2.agent.llm import call_llm, LLMUnavailableError
from crosscures_v2.agent.validator import validate_response
from crosscures_v2.memory.writer import write_episodic_memory

MAX_MARIA_QUESTIONS = 3

MARIA_OPENING = (
    "Hi, I'm Maria from CrossCures. "
    "Please go ahead and describe the health concern you'd like to report."
)

HEALTH_REPORT_SYSTEM_PROMPT = """You are Maria, a virtual healthcare assistant from CrossCures.

Your job is to help a patient document a health concern they want to report before their visit.

STRICT FORMATTING RULES — follow these without exception:
- Write in plain, natural spoken English only — as if talking to someone face to face
- Never use markdown: no headers, no bullet points, no bold, no italics, no horizontal rules, no code blocks
- Never use emojis or special symbols
- Keep every response to 1 to 3 sentences maximum
- Never ask more than one question per response
- Be warm, direct, and conversational

STRICT QUESTION LIMIT:
- You may ask at most 3 follow-up questions in total across the entire conversation
- After you have asked 3 questions, acknowledge what you heard, give a brief summary, and close warmly
- Do not ask more than one question per turn

Your role:
- Listen carefully to what the patient describes
- Ask targeted follow-up questions to clarify duration, severity, or functional impact (maximum 3 total)
- Once done, summarize what was reported in 2 to 3 sentences and say the information will be shared with the doctor

Never make diagnostic conclusions or recommend medication changes.
If the patient reports something potentially serious such as chest pain or difficulty breathing, say: "That sounds serious. Please seek emergency care or call emergency services immediately."

Keep the conversation short and focused. The patient should leave feeling heard."""

CLOSING_MESSAGE = (
    "Thank you for sharing that with me. "
    "I've noted everything you've described and will make sure your doctor has this information before your visit. "
    "Take care, and don't hesitate to reach out if anything changes."
)


def start_session(patient_id: str, db: Session) -> dict:
    session = HealthReportSessionDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        started_at=datetime.utcnow(),
        turns=[{
            "turn_id": str(uuid.uuid4()),
            "speaker": "agent",
            "content": MARIA_OPENING,
            "timestamp": datetime.utcnow().isoformat(),
        }],
        status="active",
        maria_question_count=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "initial_message": MARIA_OPENING,
        "status": session.status,
    }


def process_turn(session_id: str, patient_id: str, content: str, db: Session) -> dict:
    session = db.query(HealthReportSessionDB).filter(
        HealthReportSessionDB.id == session_id,
        HealthReportSessionDB.patient_id == patient_id,
        HealthReportSessionDB.status == "active",
    ).first()

    if not session:
        return {"error": "Session not found or not active"}

    turn_id = str(uuid.uuid4())
    turns = session.turns or []

    # If Maria has already asked MAX questions, send the closing message
    if (session.maria_question_count or 0) >= MAX_MARIA_QUESTIONS:
        agent_content = CLOSING_MESSAGE
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
        session.status = "completed"
        session.ended_at = datetime.utcnow()
        db.commit()
        return {
            "turn_id": turn_id,
            "content": agent_content,
            "session_id": session_id,
            "session_complete": True,
        }

    messages = []
    for turn in turns[-8:]:
        if turn.get("speaker") == "patient":
            messages.append({"role": "user", "content": turn["content"]})
        elif turn.get("speaker") == "agent":
            messages.append({"role": "assistant", "content": turn["content"]})

    questions_left = MAX_MARIA_QUESTIONS - (session.maria_question_count or 0)
    system = (
        HEALTH_REPORT_SYSTEM_PROMPT
        + f"\n\nYou have {questions_left} follow-up question(s) remaining. "
        "If this is your last question, also provide a brief acknowledgment summary after the question."
    )

    messages.append({"role": "user", "content": f"Patient says: {content}"})

    try:
        llm_resp = call_llm(
            system_prompt=system,
            messages=messages,
            patient_id=patient_id,
            purpose="health_report_turn",
            db=db,
            max_tokens=256,
        )
        validation = validate_response(llm_resp.content)
        agent_content = validation.sanitized_output
    except (LLMUnavailableError, Exception):
        agent_content = "Thank you for sharing that. I've noted your concern and will pass it along to your doctor."

    # Count whether this response contains a question
    contains_question = "?" in agent_content
    new_count = (session.maria_question_count or 0) + (1 if contains_question else 0)

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
    session.maria_question_count = new_count
    db.commit()

    return {
        "turn_id": turn_id,
        "content": agent_content,
        "session_id": session_id,
        "questions_remaining": max(0, MAX_MARIA_QUESTIONS - new_count),
    }


def end_session(session_id: str, patient_id: str, db: Session) -> dict:
    session = db.query(HealthReportSessionDB).filter(
        HealthReportSessionDB.id == session_id,
        HealthReportSessionDB.patient_id == patient_id,
    ).first()

    if not session:
        return {"error": "Session not found"}

    session.status = "completed"
    session.ended_at = datetime.utcnow()

    turns = session.turns or []
    patient_utterances = [t["content"] for t in turns if t.get("speaker") == "patient"]

    summary = {
        "session_id": session_id,
        "patient_turn_count": len(patient_utterances),
        "maria_questions_asked": session.maria_question_count or 0,
        "generated_at": datetime.utcnow().isoformat(),
    }
    session.summary = summary
    db.commit()

    memory_content = (
        f"Health condition report on {datetime.utcnow().date()}. "
        f"Patient described: {patient_utterances[0][:200] if patient_utterances else 'N/A'}"
    )
    write_episodic_memory(
        patient_id, session_id, memory_content, ["health_report"], db
    )

    return summary
