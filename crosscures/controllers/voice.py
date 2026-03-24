"""Voice endpoints powered by Cartesia TTS/STT."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from services.cartesia_client import synthesize_tts_wav, transcribe_audio


router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


class STTResponse(BaseModel):
    text: str


@router.get("/voice/status")
async def voice_status():
    return {"status": "ok", "service": "cartesia"}


@router.post("/voice/tts")
async def text_to_speech(request: TTSRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        audio = await synthesize_tts_wav(text=text, language=request.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(content=audio, media_type="audio/wav")


@router.post("/voice/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        text = await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=file.filename or "audio.webm",
            content_type=file.content_type,
        )
        return STTResponse(text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
