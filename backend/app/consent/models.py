from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ConsentAction(str, Enum):
    HEALTH_RECORD_STORAGE = "HEALTH_RECORD_STORAGE"
    WEARABLE_SYNC = "WEARABLE_SYNC"
    AMBIENT_LISTENING = "AMBIENT_LISTENING"
    PHYSICIAN_BRIEF_SHARING = "PHYSICIAN_BRIEF_SHARING"
    PHYSICIAN_ALERT_SHARING = "PHYSICIAN_ALERT_SHARING"
    LLM_INFERENCE = "LLM_INFERENCE"
    RESEARCH_DATA_USE = "RESEARCH_DATA_USE"


class ConsentRecord(BaseModel):
    consent_id: str
    patient_id: str
    action: ConsentAction
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    consent_version: str
    device_fingerprint: str

    model_config = {"from_attributes": True}


class ConsentError(Exception):
    def __init__(self, action: ConsentAction, patient_id: str, reason: str):
        self.action = action
        self.patient_id = patient_id
        self.reason = reason
        super().__init__(f"Consent required: {action.value} for patient {patient_id} — {reason}")
