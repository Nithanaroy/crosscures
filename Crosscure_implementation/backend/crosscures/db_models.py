"""SQLAlchemy ORM models for CrossCures."""
import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Float, Integer,
    Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "patient" | "physician"
    date_of_birth = Column(Date, nullable=True)
    npi_number = Column(String, nullable=True)  # physicians only
    specialty = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Patient relationships
    consent_records = relationship("ConsentRecordDB", back_populates="patient", foreign_keys="ConsentRecordDB.patient_id")
    health_records = relationship("HealthRecordDB", back_populates="patient")
    symptom_logs = relationship("SymptomLogDB", back_populates="patient")
    prescriptions = relationship("PrescriptionDB", back_populates="patient")
    appointments = relationship("AppointmentDB", back_populates="patient", foreign_keys="AppointmentDB.patient_id")
    clinic_sessions = relationship("ClinicSessionDB", back_populates="patient")
    memory_records = relationship("MemoryRecordDB", back_populates="patient")
    audit_entries = relationship("AuditEntryDB", back_populates="patient")
    events = relationship("EventDB", back_populates="patient")

    # Physician relationships
    linked_patients = relationship("PhysicianPatientLinkDB", back_populates="physician", foreign_keys="PhysicianPatientLinkDB.physician_id")


class PhysicianPatientLinkDB(Base):
    __tablename__ = "physician_patient_links"

    id = Column(String, primary_key=True, default=gen_uuid)
    physician_id = Column(String, ForeignKey("users.id"), nullable=False)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    linked_at = Column(DateTime, default=datetime.utcnow)

    physician = relationship("UserDB", back_populates="linked_patients", foreign_keys=[physician_id])
    patient = relationship("UserDB", foreign_keys=[patient_id])


class ConsentRecordDB(Base):
    __tablename__ = "consent_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    granted = Column(Boolean, default=False)
    granted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    consent_version = Column(String, nullable=False)
    device_fingerprint = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("UserDB", back_populates="consent_records", foreign_keys=[patient_id])


class EventDB(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=gen_uuid)
    event_type = Column(String, nullable=False)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    emitted_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, nullable=False)
    schema_version = Column(String, default="1.0.0")
    payload = Column(JSON, default=dict)
    idempotency_key = Column(String, nullable=True)

    patient = relationship("UserDB", back_populates="events")


class HealthRecordDB(Base):
    __tablename__ = "health_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    resource_type = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    display_text = Column(Text, nullable=False)
    raw_json = Column(JSON, default=dict)
    confidence = Column(Float, default=1.0)
    flags = Column(JSON, default=list)
    coding = Column(JSON, default=list)
    source_name = Column(String, nullable=True)
    upload_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("UserDB", back_populates="health_records")


class MemoryRecordDB(Base):
    __tablename__ = "memory_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    memory_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_event_ids = Column(JSON, default=list)
    source_resource_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)
    tags = Column(JSON, default=list)
    importance = Column(Float, default=0.5)

    patient = relationship("UserDB", back_populates="memory_records")


class SymptomLogDB(Base):
    __tablename__ = "symptom_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_date = Column(Date, nullable=False)
    questions = Column(JSON, default=list)
    responses = Column(JSON, default=list)
    completion_status = Column(String, default="partial")
    submitted_at = Column(DateTime, nullable=True)
    prescription_id = Column(String, nullable=True)
    day_since_start = Column(Integer, nullable=True)
    side_effects_reported = Column(JSON, default=list)

    patient = relationship("UserDB", back_populates="symptom_logs")


class AppointmentDB(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    physician_id = Column(String, nullable=True)
    physician_name = Column(String, nullable=True)
    appointment_date = Column(DateTime, nullable=False)
    location = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    brief_id = Column(String, nullable=True)
    brief_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("UserDB", back_populates="appointments", foreign_keys=[patient_id])


class PrescriptionDB(Base):
    __tablename__ = "prescriptions"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    medication_name = Column(String, nullable=False)
    medication_code = Column(String, nullable=True)
    dose = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    prescribing_physician = Column(String, nullable=True)
    start_date = Column(Date, nullable=False)
    expected_effect_onset_days = Column(Integer, default=14)
    monitoring_duration_days = Column(Integer, default=90)
    outcome_criteria = Column(JSON, default=list)
    status = Column(String, default="monitoring")
    patient_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("UserDB", back_populates="prescriptions")


class ClinicSessionDB(Base):
    __tablename__ = "clinic_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    appointment_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    audio_enabled = Column(Boolean, default=False)
    turns = Column(JSON, default=list)
    status = Column(String, default="active")
    summary = Column(JSON, nullable=True)

    patient = relationship("UserDB", back_populates="clinic_sessions")


class PhysicianBriefDB(Base):
    __tablename__ = "physician_briefs"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    physician_id = Column(String, nullable=True)
    appointment_id = Column(String, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    sections = Column(JSON, default=dict)
    citations = Column(JSON, default=list)
    delivery_status = Column(String, default="queued")
    delivered_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)


class PhysicianAlertDB(Base):
    __tablename__ = "physician_alerts"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    physician_id = Column(String, nullable=True)
    prescription_id = Column(String, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    severity = Column(String, nullable=False)
    sections = Column(JSON, default=dict)
    citations = Column(JSON, default=list)
    delivery_status = Column(String, default="queued")
    delivered_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    requires_acknowledgment = Column(Boolean, default=False)


class AuditEntryDB(Base):
    __tablename__ = "audit_entries"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    payload = Column(JSON, default=dict)
    actor = Column(String, nullable=False)
    session_id = Column(String, nullable=True)

    patient = relationship("UserDB", back_populates="audit_entries")


class WearableSampleDB(Base):
    __tablename__ = "wearable_samples"

    id = Column(String, primary_key=True, default=gen_uuid)
    sample_id = Column(String, unique=True, nullable=False)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    quantity_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    source_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
