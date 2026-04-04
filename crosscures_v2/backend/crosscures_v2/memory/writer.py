"""Memory writer — creates MemoryRecord entries from health events."""
import uuid
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from crosscures_v2.db_models import MemoryRecordDB, HealthRecordDB


def write_semantic_memory(patient_id: str, resource_ids: List[str], content: str, db: Session) -> str:
    """Write or update a semantic memory record."""
    existing = db.query(MemoryRecordDB).filter(
        MemoryRecordDB.patient_id == patient_id,
        MemoryRecordDB.memory_type == "semantic",
    ).first()

    now = datetime.utcnow()
    if existing:
        existing.content = existing.content + "\n" + content
        existing.source_resource_ids = list(set((existing.source_resource_ids or []) + resource_ids))
        existing.updated_at = now
        db.commit()
        return existing.id
    else:
        record = MemoryRecordDB(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            memory_type="semantic",
            content=content,
            source_event_ids=[],
            source_resource_ids=resource_ids,
            created_at=now,
            updated_at=now,
            tags=["health_record"],
            importance=0.8,
        )
        db.add(record)
        db.commit()
        return record.id


def write_episodic_memory(patient_id: str, event_id: str, content: str, tags: List[str], db: Session) -> str:
    """Write an episodic memory record."""
    now = datetime.utcnow()
    record = MemoryRecordDB(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        memory_type="episodic",
        content=content,
        source_event_ids=[event_id],
        source_resource_ids=[],
        created_at=now,
        updated_at=now,
        tags=tags,
        importance=0.6,
    )
    db.add(record)
    db.commit()
    return record.id


def write_prescription_memory(patient_id: str, prescription_id: str, content: str, db: Session) -> str:
    """Write or update a prescription memory record."""
    existing = db.query(MemoryRecordDB).filter(
        MemoryRecordDB.patient_id == patient_id,
        MemoryRecordDB.memory_type == "prescription",
    ).first()

    now = datetime.utcnow()
    if existing:
        existing.content = content
        existing.updated_at = now
        db.commit()
        return existing.id
    else:
        record = MemoryRecordDB(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            memory_type="prescription",
            content=content,
            source_event_ids=[],
            source_resource_ids=[prescription_id],
            created_at=now,
            updated_at=now,
            tags=["prescription", "medication"],
            importance=0.9,
        )
        db.add(record)
        db.commit()
        return record.id
