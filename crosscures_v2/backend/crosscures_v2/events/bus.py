import uuid
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from crosscures_v2.db_models import EventDB
from crosscures_v2.events.models import EventBase, EventType, EventSource


_handlers: Dict[EventType, List[Callable]] = {}


def subscribe(event_type: EventType, handler: Callable[[EventBase], None]) -> None:
    if event_type not in _handlers:
        _handlers[event_type] = []
    _handlers[event_type].append(handler)


def emit(event: EventBase, db: Session) -> str:
    # Deduplication check
    if event.idempotency_key:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        existing = db.query(EventDB).filter(
            EventDB.patient_id == event.patient_id,
            EventDB.event_type == event.event_type.value,
            EventDB.idempotency_key == event.idempotency_key,
            EventDB.emitted_at >= cutoff,
        ).first()
        if existing:
            return existing.id

    event_db = EventDB(
        id=event.event_id,
        event_type=event.event_type.value,
        patient_id=event.patient_id,
        occurred_at=event.occurred_at,
        emitted_at=datetime.utcnow(),
        source=event.source.value,
        schema_version=event.schema_version,
        payload=event.payload,
        idempotency_key=event.idempotency_key,
    )
    db.add(event_db)
    db.commit()

    # Dispatch to handlers
    handlers = _handlers.get(event.event_type, [])
    for handler in handlers:
        try:
            handler(event)
        except Exception:
            pass  # Handlers must not break event emission

    return event.event_id


def replay(patient_id: str, since: datetime, db: Session, event_types: Optional[List[EventType]] = None) -> List[EventBase]:
    query = db.query(EventDB).filter(
        EventDB.patient_id == patient_id,
        EventDB.occurred_at >= since,
    )
    if event_types:
        query = query.filter(EventDB.event_type.in_([e.value for e in event_types]))
    records = query.order_by(EventDB.occurred_at).all()
    return [
        EventBase(
            event_id=r.id,
            event_type=EventType(r.event_type),
            patient_id=r.patient_id,
            occurred_at=r.occurred_at,
            emitted_at=r.emitted_at,
            source=EventSource(r.source),
            schema_version=r.schema_version,
            payload=r.payload or {},
            idempotency_key=r.idempotency_key,
        )
        for r in records
    ]


def make_event(
    event_type: EventType,
    patient_id: str,
    source: EventSource,
    payload: dict,
    idempotency_key: Optional[str] = None,
) -> EventBase:
    return EventBase(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        patient_id=patient_id,
        occurred_at=datetime.utcnow(),
        source=source,
        payload=payload,
        idempotency_key=idempotency_key,
    )
