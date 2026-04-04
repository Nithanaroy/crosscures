"""Voice API routes — proxy for Cartesia STT/TTS."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from crosscures_v2.config import get_settings
from crosscures_v2.db_models import UserDB
from crosscures_v2.api.auth import get_current_user

router = APIRouter(prefix="/v1/voice", tags=["voice"])
settings = get_settings()

CARTESIA_BASE = "https://api.cartesia.ai"


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user: UserDB = Depends(get_current_user),
):
    """Transcribe audio using Cartesia ink-whisper STT."""
    audio_bytes = await audio.read()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CARTESIA_BASE}/audio/transcriptions",
            headers={
                "X-API-Key": settings.cartesia_api_key,
                "Cartesia-Version": settings.cartesia_version,
            },
            files={"file": (audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm")},
            data={"model": settings.cartesia_stt_model},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Cartesia STT error: {resp.text}")

    return resp.json()


class TTSRequest(BaseModel):
    text: str
    voice_id: str = ""
    output_format: str = "mp3"
    speed: float = 1.0


@router.post("/synthesize")
async def synthesize_speech(
    req: TTSRequest,
    user: UserDB = Depends(get_current_user),
):
    """Synthesize speech using Cartesia sonic-3 TTS."""
    voice_id = req.voice_id or settings.cartesia_voice_id

    payload = {
        "model_id": settings.cartesia_tts_model,
        "transcript": req.text,
        "voice": {"mode": "id", "id": voice_id},
        "output_format": {
            "container": "mp3",
            "encoding": "mp3",
            "sample_rate": 44100,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CARTESIA_BASE}/tts/bytes",
            headers={
                "X-API-Key": settings.cartesia_api_key,
                "Cartesia-Version": settings.cartesia_version,
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Cartesia TTS error: {resp.text}")

    return Response(
        content=resp.content,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"},
    )
