"""Patient API routes."""
import uuid
import json
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from crosscures_v2.database import get_db
from crosscures_v2.db_models import (
    UserDB, SymptomLogDB, AppointmentDB, PrescriptionDB, ClinicSessionDB, HealthRecordDB,
    PrevisitCallSlotDB, PrevisitSessionDB, HealthReportSessionDB,
)
from crosscures_v2.consent.models import ConsentAction
from crosscures_v2.consent.store import ConsentStore
from crosscures_v2.stages.pre_visit.question_generator import generate_checkin, inject_followup
from crosscures_v2.stages.pre_visit.brief_generator import generate_brief
from crosscures_v2.stages.clinic.session_manager import (
    start_session, process_turn, end_session,
)
from crosscures_v2.stages.previsit_call.session_manager import (
    start_session as previsit_start_session,
    process_turn as previsit_process_turn,
    end_session as previsit_end_session,
    schedule_slot as previsit_schedule_slot,
    list_slots as previsit_list_slots,
)
from crosscures_v2.stages.health_report.session_manager import (
    start_session as report_start_session,
    process_turn as report_process_turn,
    end_session as report_end_session,
)
from crosscures_v2.stages.therapy.detector import evaluate_outcomes
from crosscures_v2.ingestion.service import ingest_fhir_json, ingest_text_as_records
from crosscures_v2.events import bus as event_bus
from crosscures_v2.events.models import EventType, EventSource
from crosscures_v2.api.auth import require_patient

router = APIRouter(prefix="/v1/patient", tags=["patient"])


# ── Consent ──────────────────────────────────────────────────────────────────

class ConsentRequest(BaseModel):
    action: ConsentAction
    device_fingerprint: str = "web"


@router.get("/consent")
def get_consents(user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    store = ConsentStore(db)
    return {"consents": [c.model_dump() for c in store.get_all(user.id)]}


@router.post("/consent/grant")
def grant_consent(req: ConsentRequest, user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    store = ConsentStore(db)
    record = store.grant(user.id, req.action, req.device_fingerprint)
    event_bus.emit(event_bus.make_event(EventType.CONSENT_GRANTED, user.id, EventSource.WEB, {"action": req.action.value}), db)
    return {"consent": record.model_dump()}


@router.post("/consent/revoke")
def revoke_consent(req: ConsentRequest, user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    store = ConsentStore(db)
    record = store.revoke(user.id, req.action)
    event_bus.emit(event_bus.make_event(EventType.CONSENT_REVOKED, user.id, EventSource.WEB, {"action": req.action.value}), db)
    return {"consent": record.model_dump()}


# ── Health Records ────────────────────────────────────────────────────────────

@router.post("/records/upload")
async def upload_records(
    file: UploadFile = File(...),
    source_name: str = Form(default="Uploaded File"),
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    content = await file.read()
    upload_id = str(uuid.uuid4())
    filename = file.filename or "upload"

    if filename.endswith(".json") or file.content_type == "application/json":
        try:
            data = json.loads(content)
            result = ingest_fhir_json(user.id, data, source_name, upload_id, db)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
    else:
        # Treat as text/PDF
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            text = str(content[:2000])
        result = ingest_text_as_records(user.id, text[:5000], source_name, upload_id, db)

    return result


@router.get("/records")
def get_records(
    resource_type: Optional[str] = None,
    limit: int = 50,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    query = db.query(HealthRecordDB).filter(HealthRecordDB.patient_id == user.id)
    if resource_type:
        query = query.filter(HealthRecordDB.resource_type == resource_type)
    records = query.order_by(HealthRecordDB.created_at.desc()).limit(limit).all()
    return {
        "records": [
            {
                "id": r.id,
                "resource_type": r.resource_type,
                "display_text": r.display_text,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                "status": r.status,
                "confidence": r.confidence,
                "source_name": r.source_name,
                "flags": r.flags or [],
            }
            for r in records
        ]
    }


# ── Check-in ──────────────────────────────────────────────────────────────────

@router.get("/checkin/today")
def get_today_checkin(user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    today = date.today()
    existing = db.query(SymptomLogDB).filter(
        SymptomLogDB.patient_id == user.id,
        SymptomLogDB.session_date == today,
    ).first()

    questions = generate_checkin(user.id, today, db)

    return {
        "session_date": today.isoformat(),
        "questions": questions,
        "existing_responses": existing.responses if existing else [],
        "completion_status": existing.completion_status if existing else "not_started",
        "log_id": existing.id if existing else None,
    }


class CheckinSubmitRequest(BaseModel):
    responses: List[dict]
    session_date: Optional[str] = None
    prescription_id: Optional[str] = None
    day_since_start: Optional[int] = None


@router.post("/checkin/response")
def submit_checkin(
    req: CheckinSubmitRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    session_date_obj = date.fromisoformat(req.session_date) if req.session_date else date.today()

    existing = db.query(SymptomLogDB).filter(
        SymptomLogDB.patient_id == user.id,
        SymptomLogDB.session_date == session_date_obj,
    ).first()

    if existing:
        existing.responses = req.responses
        existing.completion_status = "completed"
        existing.submitted_at = datetime.utcnow()
        if req.prescription_id:
            existing.prescription_id = req.prescription_id
            existing.day_since_start = req.day_since_start
    else:
        questions = generate_checkin(user.id, session_date_obj, db)
        log = SymptomLogDB(
            id=str(uuid.uuid4()),
            patient_id=user.id,
            session_date=session_date_obj,
            questions=questions,
            responses=req.responses,
            completion_status="completed",
            submitted_at=datetime.utcnow(),
            prescription_id=req.prescription_id,
            day_since_start=req.day_since_start,
        )
        db.add(log)
        existing = log

    db.commit()

    event_bus.emit(
        event_bus.make_event(
            EventType.SYMPTOM_CHECKIN_SUBMITTED,
            user.id,
            EventSource.WEB,
            {"log_id": existing.id, "session_date": str(session_date_obj)},
        ),
        db,
    )

    # Check therapy deviation if prescription linked
    if req.prescription_id and req.day_since_start is not None:
        try:
            eval_result = evaluate_outcomes(user.id, req.prescription_id, req.responses, req.day_since_start, db)
        except Exception:
            eval_result = None
        return {"log_id": existing.id, "status": "completed", "evaluation": eval_result}

    return {"log_id": existing.id, "status": "completed"}


# ── Appointments ──────────────────────────────────────────────────────────────

class AppointmentCreateRequest(BaseModel):
    physician_name: str
    appointment_date: str  # ISO format
    location: Optional[str] = None
    reason: Optional[str] = None
    physician_id: Optional[str] = None


@router.get("/appointments")
def get_appointments(user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    appts = db.query(AppointmentDB).filter(
        AppointmentDB.patient_id == user.id
    ).order_by(AppointmentDB.appointment_date.desc()).all()
    return {
        "appointments": [
            {
                "id": a.id,
                "physician_name": a.physician_name,
                "appointment_date": a.appointment_date.isoformat(),
                "location": a.location,
                "reason": a.reason,
                "brief_generated": a.brief_generated,
                "brief_id": a.brief_id,
            }
            for a in appts
        ]
    }


@router.post("/appointments")
def create_appointment(
    req: AppointmentCreateRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    appt = AppointmentDB(
        id=str(uuid.uuid4()),
        patient_id=user.id,
        physician_id=req.physician_id,
        physician_name=req.physician_name,
        appointment_date=datetime.fromisoformat(req.appointment_date),
        location=req.location,
        reason=req.reason,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return {"appointment_id": appt.id, "appointment_date": appt.appointment_date.isoformat()}


@router.post("/appointments/{appointment_id}/generate-brief")
def generate_appointment_brief(
    appointment_id: str,
    force: bool = False,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    try:
        brief = generate_brief(user.id, appointment_id, db, force_regenerate=force)
        return {"brief": brief}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Clinic Session ────────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    appointment_id: Optional[str] = None
    audio_enabled: bool = False


class TurnRequest(BaseModel):
    content: str


@router.post("/clinic/session/start")
def start_clinic_session(
    req: SessionStartRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    session = start_session(user.id, db, req.appointment_id, req.audio_enabled)
    return session


@router.post("/clinic/session/{session_id}/turn")
def clinic_turn(
    session_id: str,
    req: TurnRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return process_turn(session_id, user.id, req.content, db)


@router.post("/clinic/session/{session_id}/end")
def end_clinic_session(
    session_id: str,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return end_session(session_id, user.id, db)


@router.get("/clinic/sessions")
def list_sessions(user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    sessions = db.query(ClinicSessionDB).filter(
        ClinicSessionDB.patient_id == user.id
    ).order_by(ClinicSessionDB.started_at.desc()).limit(10).all()
    return {
        "sessions": [
            {
                "id": s.id,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": s.status,
                "turn_count": len([t for t in (s.turns or []) if t.get("speaker") == "patient"]),
            }
            for s in sessions
        ]
    }


# ── Prescriptions ─────────────────────────────────────────────────────────────

class PrescriptionCreateRequest(BaseModel):
    medication_name: str
    dose: str
    frequency: str
    prescribing_physician: Optional[str] = None
    start_date: str
    medication_code: Optional[str] = None


@router.get("/prescriptions")
def get_prescriptions(user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    prescriptions = db.query(PrescriptionDB).filter(
        PrescriptionDB.patient_id == user.id
    ).all()
    return {
        "prescriptions": [
            {
                "id": p.id,
                "medication_name": p.medication_name,
                "dose": p.dose,
                "frequency": p.frequency,
                "prescribing_physician": p.prescribing_physician,
                "start_date": str(p.start_date),
                "status": p.status,
                "patient_confirmed": p.patient_confirmed,
                "monitoring_duration_days": p.monitoring_duration_days,
            }
            for p in prescriptions
        ]
    }


@router.post("/prescriptions")
def create_prescription(
    req: PrescriptionCreateRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    from crosscures_v2.memory.writer import write_prescription_memory
    from datetime import date as date_type

    p = PrescriptionDB(
        id=str(uuid.uuid4()),
        patient_id=user.id,
        medication_name=req.medication_name,
        dose=req.dose,
        frequency=req.frequency,
        prescribing_physician=req.prescribing_physician,
        start_date=date_type.fromisoformat(req.start_date),
        medication_code=req.medication_code,
        status="monitoring",
        patient_confirmed=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    memory_content = f"Active prescription: {p.medication_name} {p.dose} {p.frequency}. Started {p.start_date}. Prescriber: {p.prescribing_physician or 'unknown'}."
    write_prescription_memory(user.id, p.id, memory_content, db)

    event_bus.emit(
        event_bus.make_event(
            EventType.PRESCRIPTION_RECORDED,
            user.id,
            EventSource.WEB,
            {"prescription_id": p.id, "medication_name": p.medication_name},
        ),
        db,
    )

    return {"prescription_id": p.id}


@router.post("/prescriptions/{prescription_id}/confirm")
def confirm_prescription(
    prescription_id: str,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    p = db.query(PrescriptionDB).filter(
        PrescriptionDB.id == prescription_id,
        PrescriptionDB.patient_id == user.id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prescription not found")
    p.patient_confirmed = True
    p.status = "monitoring"
    db.commit()
    return {"status": "confirmed"}


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/profile")
def get_profile(user: UserDB = Depends(require_patient), db: Session = Depends(get_db)):
    from crosscures_v2.consent.store import ConsentStore
    store = ConsentStore(db)
    consents = store.get_all(user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "date_of_birth": str(user.date_of_birth) if user.date_of_birth else None,
        "consents": [c.model_dump() for c in consents],
    }


# ── Pre-Visit Call ─────────────────────────────────────────────────────────────

class PrevisitScheduleRequest(BaseModel):
    scheduled_at: str  # ISO datetime
    appointment_id: Optional[str] = None


@router.post("/previsit/schedule")
def schedule_previsit(
    req: PrevisitScheduleRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    try:
        scheduled_dt = datetime.fromisoformat(req.scheduled_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")
    return previsit_schedule_slot(user.id, scheduled_dt, db, req.appointment_id)


@router.get("/previsit/slots")
def get_previsit_slots(
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return {"slots": previsit_list_slots(user.id, db)}


@router.post("/previsit/session/start")
def start_previsit_session(
    slot_id: Optional[str] = Body(default=None),
    appointment_id: Optional[str] = Body(default=None),
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return previsit_start_session(user.id, db, slot_id, appointment_id)


@router.post("/previsit/session/{session_id}/turn")
def previsit_turn(
    session_id: str,
    req: TurnRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return previsit_process_turn(session_id, user.id, req.content, db)


@router.post("/previsit/session/{session_id}/end")
def end_previsit_session(
    session_id: str,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return previsit_end_session(session_id, user.id, db)


# ── Health Condition Report ────────────────────────────────────────────────────

@router.post("/health-report/session/start")
def start_health_report_session(
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return report_start_session(user.id, db)


@router.post("/health-report/session/{session_id}/turn")
def health_report_turn(
    session_id: str,
    req: TurnRequest,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return report_process_turn(session_id, user.id, req.content, db)


@router.post("/health-report/session/{session_id}/end")
def end_health_report_session(
    session_id: str,
    user: UserDB = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return report_end_session(session_id, user.id, db)
