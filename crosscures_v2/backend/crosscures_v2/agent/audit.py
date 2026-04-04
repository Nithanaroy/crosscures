import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from crosscures_v2.db_models import AuditEntryDB


def log_audit(
    db: Session,
    patient_id: str,
    event_type: str,
    payload: dict,
    actor: str = "agent",
    session_id: Optional[str] = None,
):
    entry = AuditEntryDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        event_type=event_type,
        occurred_at=datetime.utcnow(),
        payload=payload,
        actor=actor,
        session_id=session_id,
    )
    db.add(entry)
    db.commit()
