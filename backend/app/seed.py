"""Seed demo users and data for CrossCures."""
import uuid
from datetime import date, datetime, timedelta
from app.database import SessionLocal, init_db
from app.db_models import (
    UserDB, ConsentRecordDB, HealthRecordDB, PrescriptionDB,
    AppointmentDB, PhysicianPatientLinkDB, SymptomLogDB
)
from app.api.auth import hash_password
from app.config import get_settings

settings = get_settings()

def seed():
    init_db()
    db = SessionLocal()

    # Clean existing demo data
    from app.db_models import (
        ConsentRecordDB, HealthRecordDB, PrescriptionDB,
        AppointmentDB, PhysicianPatientLinkDB, SymptomLogDB,
        ClinicSessionDB, AuditEntryDB, EventDB, MemoryRecordDB
    )

    for email in ["patient@demo.com", "physician@demo.com"]:
        user = db.query(UserDB).filter(UserDB.email == email).first()
        if user:
            # Delete related records first
            for model in [ConsentRecordDB, HealthRecordDB, PrescriptionDB, SymptomLogDB,
                         ClinicSessionDB, AuditEntryDB, EventDB, MemoryRecordDB]:
                try:
                    db.query(model).filter(model.patient_id == user.id).delete(synchronize_session=False)
                except Exception:
                    pass
            try:
                db.query(AppointmentDB).filter(AppointmentDB.patient_id == user.id).delete(synchronize_session=False)
            except Exception:
                pass
            try:
                db.query(PhysicianPatientLinkDB).filter(
                    (PhysicianPatientLinkDB.physician_id == user.id) |
                    (PhysicianPatientLinkDB.patient_id == user.id)
                ).delete(synchronize_session=False)
            except Exception:
                pass
            db.delete(user)
    db.commit()

    # Create demo physician
    physician = UserDB(
        id=str(uuid.uuid4()),
        email="physician@demo.com",
        hashed_password=hash_password("demo1234"),
        full_name="Dr. Sarah Chen",
        role="physician",
        specialty="Internal Medicine",
        npi_number="1234567890",
    )
    db.add(physician)

    # Create demo patient
    patient = UserDB(
        id=str(uuid.uuid4()),
        email="patient@demo.com",
        hashed_password=hash_password("demo1234"),
        full_name="James Mitchell",
        role="patient",
        date_of_birth=date(1975, 8, 23),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    db.refresh(physician)

    # Consents for patient
    for action in [
        "HEALTH_RECORD_STORAGE", "LLM_INFERENCE",
        "PHYSICIAN_BRIEF_SHARING", "PHYSICIAN_ALERT_SHARING",
        "WEARABLE_SYNC", "AMBIENT_LISTENING",
    ]:
        consent = ConsentRecordDB(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            action=action,
            granted=True,
            granted_at=datetime.utcnow(),
            consent_version=settings.consent_version,
            device_fingerprint="seed",
        )
        db.add(consent)

    # Link physician to patient
    link = PhysicianPatientLinkDB(
        id=str(uuid.uuid4()),
        physician_id=physician.id,
        patient_id=patient.id,
    )
    db.add(link)

    # Health records
    records = [
        {"resource_type": "Condition", "display_text": "Condition: Type 2 Diabetes Mellitus", "status": "active"},
        {"resource_type": "Condition", "display_text": "Condition: Essential Hypertension", "status": "active"},
        {"resource_type": "AllergyIntolerance", "display_text": "Allergy: Penicillin (severe)", "status": "active"},
        {"resource_type": "MedicationRequest", "display_text": "Medication: Metformin 1000mg twice daily", "status": "active"},
        {"resource_type": "MedicationRequest", "display_text": "Medication: Lisinopril 10mg once daily", "status": "active"},
        {"resource_type": "Observation", "display_text": "Lab/Observation: HbA1c: 7.2% (good control)", "status": "final"},
        {"resource_type": "Observation", "display_text": "Lab/Observation: Blood Pressure: 135/85 mmHg", "status": "final"},
        {"resource_type": "DiagnosticReport", "display_text": "Report: Comprehensive Metabolic Panel — within normal limits", "status": "final"},
    ]
    for r in records:
        record = HealthRecordDB(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            occurred_at=datetime.utcnow() - timedelta(days=30),
            confidence=1.0,
            flags=[],
            coding=[],
            source_name="Primary Care EHR",
            upload_id=str(uuid.uuid4()),
            **r,
        )
        db.add(record)

    # Prescription
    prescription = PrescriptionDB(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        medication_name="Metformin",
        dose="1000mg",
        frequency="twice daily",
        prescribing_physician="Dr. Sarah Chen",
        start_date=date.today() - timedelta(days=14),
        expected_effect_onset_days=14,
        monitoring_duration_days=90,
        status="monitoring",
        patient_confirmed=True,
    )
    db.add(prescription)

    # Appointment (in 5 days)
    appointment = AppointmentDB(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        physician_id=physician.id,
        physician_name="Dr. Sarah Chen",
        appointment_date=datetime.utcnow() + timedelta(days=5),
        location="University Medical Center",
        reason="Diabetes follow-up and blood pressure check",
    )
    db.add(appointment)

    # Symptom logs (last 3 days)
    for i in range(3):
        log_date = date.today() - timedelta(days=i)
        log = SymptomLogDB(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            session_date=log_date,
            questions=[],
            responses=[
                {"question_id": "base_pain", "value": 3 + i, "answered_at": datetime.utcnow().isoformat(), "skipped": False},
                {"question_id": "base_fatigue", "value": 4, "answered_at": datetime.utcnow().isoformat(), "skipped": False},
                {"question_id": "base_sleep", "value": "7 hours", "answered_at": datetime.utcnow().isoformat(), "skipped": False},
                {"question_id": "base_mood", "value": 7, "answered_at": datetime.utcnow().isoformat(), "skipped": False},
                {"question_id": "diabetes_glucose", "value": "142 mg/dL", "answered_at": datetime.utcnow().isoformat(), "skipped": False},
            ],
            completion_status="completed",
            submitted_at=datetime.utcnow() - timedelta(days=i),
        )
        db.add(log)

    db.commit()
    print(f"Demo seeded successfully!")
    print(f"Patient: patient@demo.com / demo1234 (James Mitchell)")
    print(f"Physician: physician@demo.com / demo1234 (Dr. Sarah Chen)")
    print(f"Appointment in 5 days at University Medical Center")
    db.close()

if __name__ == "__main__":
    seed()
