"""Health record ingestion service."""
import uuid
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from crosscures_v2.db_models import HealthRecordDB
from crosscures_v2.consent.models import ConsentAction
from crosscures_v2.consent.store import ConsentStore
from crosscures_v2.events import bus as event_bus
from crosscures_v2.events.models import EventType, EventSource


SUPPORTED_FHIR_TYPES = {
    "Patient", "Condition", "MedicationRequest", "MedicationStatement",
    "Observation", "DiagnosticReport", "AllergyIntolerance", "Procedure",
    "Encounter", "DocumentReference",
}


def ingest_fhir_json(patient_id: str, raw_data: dict, source_name: str, upload_id: str, db: Session) -> dict:
    """Parse and ingest a FHIR JSON bundle or resource."""
    consent_store = ConsentStore(db)
    consent_store.require(patient_id, ConsentAction.HEALTH_RECORD_STORAGE)

    records_extracted = 0
    records_failed = 0
    warnings = []
    extracted = []

    resources = []
    if raw_data.get("resourceType") == "Bundle":
        for entry in raw_data.get("entry", []):
            resource = entry.get("resource")
            if resource:
                resources.append(resource)
    elif "resourceType" in raw_data:
        resources.append(raw_data)
    else:
        warnings.append("No FHIR resourceType found. Treating as unknown format.")
        resources.append(raw_data)

    for resource in resources:
        resource_type = resource.get("resourceType", "Unknown")
        if resource_type not in SUPPORTED_FHIR_TYPES and resource_type != "Unknown":
            warnings.append(f"Unsupported resource type skipped: {resource_type}")
            continue

        try:
            display_text = _extract_display(resource)
            occurred_at = _extract_date(resource)
            coding = _extract_coding(resource)
            resource_id = resource.get("id", str(uuid.uuid4()))

            # Deduplicate by resource_id + type
            existing = db.query(HealthRecordDB).filter(
                HealthRecordDB.patient_id == patient_id,
                HealthRecordDB.id == resource_id,
            ).first()
            if existing:
                warnings.append(f"Duplicate resource skipped: {resource_id}")
                continue

            record = HealthRecordDB(
                id=resource_id,
                patient_id=patient_id,
                resource_type=resource_type,
                occurred_at=occurred_at,
                status=resource.get("status"),
                display_text=display_text,
                raw_json=resource,
                confidence=1.0,
                flags=[],
                coding=coding,
                source_name=source_name,
                upload_id=upload_id,
            )
            db.add(record)
            records_extracted += 1
            extracted.append({"id": resource_id, "type": resource_type, "display": display_text})

            event_bus.emit(
                event_bus.make_event(
                    event_type=EventType.HEALTH_RECORD_INGESTED,
                    patient_id=patient_id,
                    source=EventSource.WEB,
                    payload={"resource_id": resource_id, "resource_type": resource_type},
                ),
                db,
            )
        except Exception as e:
            records_failed += 1
            warnings.append(f"Failed to process resource: {str(e)}")

    db.commit()

    return {
        "upload_id": upload_id,
        "records_extracted": records_extracted,
        "records_failed": records_failed,
        "warnings": warnings,
        "extracted_resources": extracted,
    }


def ingest_text_as_records(patient_id: str, text: str, source_name: str, upload_id: str, db: Session, llm_extracted: Optional[dict] = None) -> dict:
    """Ingest extracted text (from PDF) as health records."""
    consent_store = ConsentStore(db)
    consent_store.require(patient_id, ConsentAction.HEALTH_RECORD_STORAGE)

    records_extracted = 0
    warnings = ["PDF-extracted records have confidence < 1.0"]

    if llm_extracted and "resources" in llm_extracted:
        for res in llm_extracted["resources"]:
            try:
                record = HealthRecordDB(
                    id=str(uuid.uuid4()),
                    patient_id=patient_id,
                    resource_type=res.get("type", "DocumentReference"),
                    occurred_at=None,
                    status="active",
                    display_text=res.get("display", text[:200]),
                    raw_json=res,
                    confidence=0.7,
                    flags=["pdf_extracted"],
                    coding=[],
                    source_name=source_name,
                    upload_id=upload_id,
                )
                db.add(record)
                records_extracted += 1
            except Exception as e:
                warnings.append(str(e))
    else:
        # Store as a single DocumentReference
        record = HealthRecordDB(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            resource_type="DocumentReference",
            occurred_at=datetime.utcnow(),
            status="current",
            display_text=source_name + ": " + text[:300],
            raw_json={"text": text, "source": source_name},
            confidence=0.6,
            flags=["pdf_extracted", "no_structured_extraction"],
            coding=[],
            source_name=source_name,
            upload_id=upload_id,
        )
        db.add(record)
        records_extracted = 1

    db.commit()

    event_bus.emit(
        event_bus.make_event(
            event_type=EventType.HEALTH_RECORD_INGESTED,
            patient_id=patient_id,
            source=EventSource.WEB,
            payload={"upload_id": upload_id, "source_name": source_name, "pdf": True},
        ),
        db,
    )

    return {
        "upload_id": upload_id,
        "records_extracted": records_extracted,
        "records_failed": 0,
        "warnings": warnings,
        "extracted_resources": [],
    }


def _extract_display(resource: dict) -> str:
    rt = resource.get("resourceType", "")
    if rt == "Condition":
        code = resource.get("code", {})
        text = code.get("text") or (code.get("coding", [{}])[0].get("display", "") if code.get("coding") else "")
        return f"Condition: {text or 'Unknown condition'}"
    elif rt in ("MedicationRequest", "MedicationStatement"):
        med = resource.get("medicationCodeableConcept", resource.get("medication", {}))
        if isinstance(med, dict):
            text = med.get("text") or (med.get("coding", [{}])[0].get("display", "") if med.get("coding") else "")
        else:
            text = str(med)
        return f"Medication: {text or 'Unknown medication'}"
    elif rt == "Observation":
        code = resource.get("code", {})
        text = code.get("text") or "Observation"
        value = resource.get("valueQuantity", {})
        val_str = f": {value.get('value')} {value.get('unit', '')}" if value else ""
        return f"Lab/Observation: {text}{val_str}"
    elif rt == "AllergyIntolerance":
        code = resource.get("code", {})
        text = code.get("text") or "Unknown allergen"
        return f"Allergy: {text}"
    elif rt == "DiagnosticReport":
        code = resource.get("code", {})
        text = code.get("text") or "Diagnostic Report"
        return f"Report: {text}"
    elif rt == "Procedure":
        code = resource.get("code", {})
        text = code.get("text") or "Procedure"
        return f"Procedure: {text}"
    elif rt == "Encounter":
        return f"Encounter: {resource.get('type', [{}])[0].get('text', 'Visit') if resource.get('type') else 'Visit'}"
    elif rt == "Patient":
        name = resource.get("name", [{}])[0] if resource.get("name") else {}
        full = " ".join(name.get("given", [])) + " " + name.get("family", "")
        return f"Patient: {full.strip()}"
    elif rt == "DocumentReference":
        return f"Document: {resource.get('description', 'Clinical Document')}"
    return f"{rt}: {resource.get('id', 'unknown')}"


def _extract_date(resource: dict) -> Optional[datetime]:
    for key in ("effectiveDateTime", "recordedDate", "authoredOn", "date", "period", "onsetDateTime"):
        val = resource.get(key)
        if val and isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                pass
    return None


def _extract_coding(resource: dict) -> list:
    coding_list = []
    for key in ("code", "medicationCodeableConcept", "medication", "category"):
        val = resource.get(key)
        if isinstance(val, dict):
            for c in val.get("coding", []):
                coding_list.append({
                    "system": c.get("system", ""),
                    "code": c.get("code", ""),
                    "display": c.get("display"),
                })
    return coding_list
