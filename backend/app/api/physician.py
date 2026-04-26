"""Physician API routes."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import UserDB, PhysicianBriefDB, PhysicianAlertDB, PhysicianPatientLinkDB
from app.api.auth import require_physician

router = APIRouter(prefix="/v1/physician", tags=["physician"])


@router.get("/dashboard")
def get_dashboard(user: UserDB = Depends(require_physician), db: Session = Depends(get_db)):
    """Dashboard: unread briefs and unacknowledged alerts."""
    # Get linked patient IDs
    links = db.query(PhysicianPatientLinkDB).filter(
        PhysicianPatientLinkDB.physician_id == user.id
    ).all()
    patient_ids = [l.patient_id for l in links]

    unread_briefs = []
    unacked_alerts = []

    if patient_ids:
        briefs = db.query(PhysicianBriefDB).filter(
            PhysicianBriefDB.patient_id.in_(patient_ids),
            PhysicianBriefDB.acknowledged_at == None,
        ).order_by(PhysicianBriefDB.generated_at.desc()).limit(20).all()

        alerts = db.query(PhysicianAlertDB).filter(
            PhysicianAlertDB.patient_id.in_(patient_ids),
            PhysicianAlertDB.acknowledged_at == None,
        ).order_by(PhysicianAlertDB.generated_at.desc()).limit(20).all()

        for b in briefs:
            patient = db.query(UserDB).filter(UserDB.id == b.patient_id).first()
            unread_briefs.append({
                "brief_id": b.id,
                "patient_id": b.patient_id,
                "patient_name": patient.full_name if patient else "Unknown",
                "generated_at": b.generated_at.isoformat(),
                "appointment_id": b.appointment_id,
                "delivery_status": b.delivery_status,
            })

        for a in alerts:
            patient = db.query(UserDB).filter(UserDB.id == a.patient_id).first()
            unacked_alerts.append({
                "alert_id": a.id,
                "patient_id": a.patient_id,
                "patient_name": patient.full_name if patient else "Unknown",
                "severity": a.severity,
                "generated_at": a.generated_at.isoformat(),
                "requires_acknowledgment": a.requires_acknowledgment,
            })

    return {
        "unread_briefs": unread_briefs,
        "unacknowledged_alerts": unacked_alerts,
        "linked_patient_count": len(patient_ids),
    }


@router.get("/patients")
def get_patients(user: UserDB = Depends(require_physician), db: Session = Depends(get_db)):
    links = db.query(PhysicianPatientLinkDB).filter(
        PhysicianPatientLinkDB.physician_id == user.id
    ).all()
    patients = []
    for link in links:
        patient = db.query(UserDB).filter(UserDB.id == link.patient_id).first()
        if patient:
            # Count recent briefs and alerts
            brief_count = db.query(PhysicianBriefDB).filter(PhysicianBriefDB.patient_id == patient.id).count()
            alert_count = db.query(PhysicianAlertDB).filter(
                PhysicianAlertDB.patient_id == patient.id,
                PhysicianAlertDB.acknowledged_at == None,
            ).count()
            patients.append({
                "id": patient.id,
                "full_name": patient.full_name,
                "email": patient.email,
                "linked_at": link.linked_at.isoformat(),
                "brief_count": brief_count,
                "unacknowledged_alert_count": alert_count,
            })
    return {"patients": patients}


@router.get("/patients/{patient_id}/briefs")
def get_patient_briefs(
    patient_id: str,
    user: UserDB = Depends(require_physician),
    db: Session = Depends(get_db),
):
    _verify_patient_link(user.id, patient_id, db)
    briefs = db.query(PhysicianBriefDB).filter(
        PhysicianBriefDB.patient_id == patient_id
    ).order_by(PhysicianBriefDB.generated_at.desc()).all()
    return {"briefs": [_brief_summary(b) for b in briefs]}


@router.get("/briefs/{brief_id}")
def get_brief(
    brief_id: str,
    user: UserDB = Depends(require_physician),
    db: Session = Depends(get_db),
):
    brief = db.query(PhysicianBriefDB).filter(PhysicianBriefDB.id == brief_id).first()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    _verify_patient_link(user.id, brief.patient_id, db)
    patient = db.query(UserDB).filter(UserDB.id == brief.patient_id).first()
    sections = dict(brief.sections or {})
    if "patient_summary" not in sections:
        sections["patient_summary"] = sections.get("patient_snapshot") or "No patient summary available"
    return {
        "brief_id": brief.id,
        "patient_id": brief.patient_id,
        "patient_name": patient.full_name if patient else "Unknown",
        "appointment_id": brief.appointment_id,
        "generated_at": brief.generated_at.isoformat(),
        "sections": sections,
        "citations": brief.citations or [],
        "delivery_status": brief.delivery_status,
        "acknowledged_at": brief.acknowledged_at.isoformat() if brief.acknowledged_at else None,
    }


@router.get("/patients/{patient_id}/alerts")
def get_patient_alerts(
    patient_id: str,
    user: UserDB = Depends(require_physician),
    db: Session = Depends(get_db),
):
    _verify_patient_link(user.id, patient_id, db)
    alerts = db.query(PhysicianAlertDB).filter(
        PhysicianAlertDB.patient_id == patient_id
    ).order_by(PhysicianAlertDB.generated_at.desc()).all()
    return {"alerts": [_alert_summary(a) for a in alerts]}


@router.get("/alerts/{alert_id}")
def get_alert(
    alert_id: str,
    user: UserDB = Depends(require_physician),
    db: Session = Depends(get_db),
):
    alert = db.query(PhysicianAlertDB).filter(PhysicianAlertDB.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    _verify_patient_link(user.id, alert.patient_id, db)
    patient = db.query(UserDB).filter(UserDB.id == alert.patient_id).first()
    return {
        "alert_id": alert.id,
        "patient_id": alert.patient_id,
        "patient_name": patient.full_name if patient else "Unknown",
        "prescription_id": alert.prescription_id,
        "severity": alert.severity,
        "generated_at": alert.generated_at.isoformat(),
        "sections": alert.sections,
        "requires_acknowledgment": alert.requires_acknowledgment,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "delivery_status": alert.delivery_status,
    }


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    user: UserDB = Depends(require_physician),
    db: Session = Depends(get_db),
):
    alert = db.query(PhysicianAlertDB).filter(PhysicianAlertDB.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    _verify_patient_link(user.id, alert.patient_id, db)
    alert.acknowledged_at = datetime.utcnow()
    db.commit()
    return {"acknowledged_at": alert.acknowledged_at.isoformat()}


@router.post("/briefs/{brief_id}/acknowledge")
def acknowledge_brief(
    brief_id: str,
    user: UserDB = Depends(require_physician),
    db: Session = Depends(get_db),
):
    brief = db.query(PhysicianBriefDB).filter(PhysicianBriefDB.id == brief_id).first()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    _verify_patient_link(user.id, brief.patient_id, db)
    brief.acknowledged_at = datetime.utcnow()
    db.commit()
    return {"acknowledged_at": brief.acknowledged_at.isoformat()}


def _verify_patient_link(physician_id: str, patient_id: str, db: Session):
    link = db.query(PhysicianPatientLinkDB).filter(
        PhysicianPatientLinkDB.physician_id == physician_id,
        PhysicianPatientLinkDB.patient_id == patient_id,
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="Patient not linked to this physician")


def _brief_summary(b: PhysicianBriefDB) -> dict:
    sections = dict(b.sections or {})
    if "patient_summary" not in sections:
        sections["patient_summary"] = sections.get("patient_snapshot") or "No patient summary available"
    return {
        "brief_id": b.id,
        "patient_id": b.patient_id,
        "appointment_id": b.appointment_id,
        "generated_at": b.generated_at.isoformat(),
        "delivery_status": b.delivery_status,
        "acknowledged_at": b.acknowledged_at.isoformat() if b.acknowledged_at else None,
        "sections_preview": {k: (str(v)[:100] if v else None) for k, v in sections.items()},
    }


def _alert_summary(a: PhysicianAlertDB) -> dict:
    return {
        "alert_id": a.id,
        "patient_id": a.patient_id,
        "severity": a.severity,
        "generated_at": a.generated_at.isoformat(),
        "requires_acknowledgment": a.requires_acknowledgment,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "delivery_status": a.delivery_status,
    }
