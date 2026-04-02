"""User registration and auth routes."""
import uuid
from datetime import date as date_type, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from ..db_models import UserDB, PhysicianPatientLinkDB
from ..consent.models import ConsentAction
from ..consent.store import ConsentStore
from .auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str  # "patient" | "physician"
    date_of_birth: Optional[str] = None
    npi_number: Optional[str] = None
    specialty: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LinkPhysicianRequest(BaseModel):
    physician_email: str


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if req.role not in ("patient", "physician"):
        raise HTTPException(status_code=400, detail="Role must be 'patient' or 'physician'")

    dob = None
    if req.date_of_birth:
        try:
            dob = date_type.fromisoformat(req.date_of_birth)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_of_birth format (use YYYY-MM-DD)")

    user = UserDB(
        id=str(uuid.uuid4()),
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        date_of_birth=dob,
        npi_number=req.npi_number,
        specialty=req.specialty,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-grant core consents for patients on registration
    if req.role == "patient":
        store = ConsentStore(db)
        for action in (
            ConsentAction.HEALTH_RECORD_STORAGE,
            ConsentAction.LLM_INFERENCE,
            ConsentAction.PHYSICIAN_BRIEF_SHARING,
            ConsentAction.PHYSICIAN_ALERT_SHARING,
        ):
            store.grant(user.id, action, "web")

    token = create_access_token({"sub": user.id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower(), UserDB.is_active == True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token({"sub": user.id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@router.get("/me")
def get_me(user: UserDB = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "specialty": user.specialty,
        "npi_number": user.npi_number,
    }


@router.post("/link-physician")
def link_physician(
    req: LinkPhysicianRequest,
    user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can link physicians")

    physician = db.query(UserDB).filter(
        UserDB.email == req.physician_email.lower(),
        UserDB.role == "physician",
    ).first()
    if not physician:
        raise HTTPException(status_code=404, detail="Physician not found")

    existing_link = db.query(PhysicianPatientLinkDB).filter(
        PhysicianPatientLinkDB.physician_id == physician.id,
        PhysicianPatientLinkDB.patient_id == user.id,
    ).first()
    if existing_link:
        return {"status": "already_linked", "physician_name": physician.full_name}

    link = PhysicianPatientLinkDB(
        id=str(uuid.uuid4()),
        physician_id=physician.id,
        patient_id=user.id,
    )
    db.add(link)
    db.commit()
    return {"status": "linked", "physician_name": physician.full_name, "physician_id": physician.id}
