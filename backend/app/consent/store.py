import uuid
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from app.db_models import ConsentRecordDB
from app.config import get_settings
from app.consent.models import ConsentAction, ConsentRecord, ConsentError

settings = get_settings()


class ConsentStore:
    def __init__(self, db: Session):
        self.db = db

    def grant(self, patient_id: str, action: ConsentAction, device_fingerprint: str = "web") -> ConsentRecord:
        existing = self.db.query(ConsentRecordDB).filter(
            ConsentRecordDB.patient_id == patient_id,
            ConsentRecordDB.action == action.value,
        ).first()

        now = datetime.utcnow()
        if existing:
            existing.granted = True
            existing.granted_at = now
            existing.revoked_at = None
            existing.consent_version = settings.consent_version
            self.db.commit()
            self.db.refresh(existing)
            return ConsentRecord(
                consent_id=existing.id,
                patient_id=existing.patient_id,
                action=ConsentAction(existing.action),
                granted=existing.granted,
                granted_at=existing.granted_at,
                revoked_at=existing.revoked_at,
                consent_version=existing.consent_version,
                device_fingerprint=existing.device_fingerprint,
            )

        record = ConsentRecordDB(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            action=action.value,
            granted=True,
            granted_at=now,
            consent_version=settings.consent_version,
            device_fingerprint=device_fingerprint,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return ConsentRecord(
            consent_id=record.id,
            patient_id=record.patient_id,
            action=ConsentAction(record.action),
            granted=record.granted,
            granted_at=record.granted_at,
            revoked_at=record.revoked_at,
            consent_version=record.consent_version,
            device_fingerprint=record.device_fingerprint,
        )

    def revoke(self, patient_id: str, action: ConsentAction) -> ConsentRecord:
        record = self.db.query(ConsentRecordDB).filter(
            ConsentRecordDB.patient_id == patient_id,
            ConsentRecordDB.action == action.value,
        ).first()

        if record:
            record.granted = False
            record.revoked_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(record)
            return ConsentRecord(
                consent_id=record.id,
                patient_id=record.patient_id,
                action=ConsentAction(record.action),
                granted=record.granted,
                granted_at=record.granted_at,
                revoked_at=record.revoked_at,
                consent_version=record.consent_version,
                device_fingerprint=record.device_fingerprint,
            )
        raise ConsentError(action, patient_id, "not_granted")

    def check(self, patient_id: str, action: ConsentAction) -> bool:
        record = self.db.query(ConsentRecordDB).filter(
            ConsentRecordDB.patient_id == patient_id,
            ConsentRecordDB.action == action.value,
            ConsentRecordDB.granted == True,
        ).first()
        return record is not None and record.revoked_at is None

    def require(self, patient_id: str, action: ConsentAction) -> None:
        if not self.check(patient_id, action):
            raise ConsentError(action, patient_id, "not_granted")

    def get_all(self, patient_id: str) -> List[ConsentRecord]:
        records = self.db.query(ConsentRecordDB).filter(
            ConsentRecordDB.patient_id == patient_id
        ).all()
        return [
            ConsentRecord(
                consent_id=r.id,
                patient_id=r.patient_id,
                action=ConsentAction(r.action),
                granted=r.granted,
                granted_at=r.granted_at,
                revoked_at=r.revoked_at,
                consent_version=r.consent_version,
                device_fingerprint=r.device_fingerprint,
            )
            for r in records
        ]
