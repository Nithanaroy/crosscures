from enum import Enum
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class EventType(str, Enum):
    HEALTH_RECORD_INGESTED = "HEALTH_RECORD_INGESTED"
    WEARABLE_SYNC_COMPLETED = "WEARABLE_SYNC_COMPLETED"
    SYMPTOM_CHECKIN_SUBMITTED = "SYMPTOM_CHECKIN_SUBMITTED"
    CLINIC_SESSION_STARTED = "CLINIC_SESSION_STARTED"
    CLINIC_SESSION_ENDED = "CLINIC_SESSION_ENDED"
    PRESCRIPTION_RECORDED = "PRESCRIPTION_RECORDED"
    THERAPY_CHECKIN_SUBMITTED = "THERAPY_CHECKIN_SUBMITTED"
    OUTCOME_DEVIATION_DETECTED = "OUTCOME_DEVIATION_DETECTED"
    BRIEF_GENERATED = "BRIEF_GENERATED"
    ALERT_GENERATED = "ALERT_GENERATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"


class EventSource(str, Enum):
    MOBILE = "mobile"
    WEARABLE = "wearable"
    EHR = "ehr"
    AGENT = "agent"
    PHYSICIAN = "physician"
    WEB = "web"


class EventBase(BaseModel):
    event_id: str
    event_type: EventType
    patient_id: str
    occurred_at: datetime
    emitted_at: Optional[datetime] = None
    source: EventSource
    schema_version: str = "1.0.0"
    payload: dict = {}
    idempotency_key: Optional[str] = None
