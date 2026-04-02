"""CrossCures FastAPI Application Entry Point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from crosscures.database import init_db
from crosscures.config import get_settings
from crosscures.api.users import router as users_router
from crosscures.api.patient import router as patient_router
from crosscures.api.physician import router as physician_router
from crosscures.api.voice import router as voice_router

settings = get_settings()

app = FastAPI(
    title="CrossCures API",
    description="AI-powered health companion for patients and physicians",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    print("CrossCures API started. Database initialized.")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from crosscures.consent.models import ConsentError
    if isinstance(exc, ConsentError):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "CONSENT_REQUIRED",
                    "message": str(exc),
                    "details": {"action": exc.action.value, "reason": exc.reason},
                }
            },
        )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": str(exc), "details": None}},
    )


app.include_router(users_router)
app.include_router(patient_router)
app.include_router(physician_router)
app.include_router(voice_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CrossCures API", "version": "1.0.0"}


@app.get("/")
def root():
    return {
        "service": "CrossCures API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
