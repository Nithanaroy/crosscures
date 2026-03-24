"""Cartesia API client helpers for TTS and STT."""

import os

import httpx


CARTESIA_BASE_URL = "https://api.cartesia.ai"
CARTESIA_VERSION = os.getenv("CARTESIA_VERSION", "2026-03-01")
CARTESIA_TTS_MODEL = os.getenv("CARTESIA_TTS_MODEL", "sonic-3")
CARTESIA_STT_MODEL = os.getenv("CARTESIA_STT_MODEL", "ink-whisper")
CARTESIA_VOICE_ID = os.getenv(
    "CARTESIA_VOICE_ID",
    "694f9389-aac1-45b6-b726-9d9369183238",
)


def _auth_headers() -> dict[str, str]:
    api_key = os.getenv("CARTESIA_API_KEY")
    if not api_key:
        raise RuntimeError("CARTESIA_API_KEY is not set")

    return {
        "Authorization": f"Bearer {api_key}",
        "Cartesia-Version": CARTESIA_VERSION,
    }


async def synthesize_tts_wav(text: str, language: str = "en") -> bytes:
    """Generate WAV bytes from text via Cartesia TTS."""
    headers = {
        **_auth_headers(),
        "Content-Type": "application/json",
    }
    payload = {
        "model_id": CARTESIA_TTS_MODEL,
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": CARTESIA_VOICE_ID,
        },
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 44100,
        },
        "language": language,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CARTESIA_BASE_URL}/tts/bytes",
            headers=headers,
            json=payload,
        )

    if resp.status_code >= 400:
        raise RuntimeError(f"Cartesia TTS failed ({resp.status_code}): {resp.text[:500]}")

    return resp.content


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    content_type: str | None,
    language: str = "en",
) -> str:
    """Transcribe an uploaded audio payload via Cartesia STT."""
    headers = _auth_headers()
    files = {
        "file": (
            filename or "audio.webm",
            audio_bytes,
            content_type or "audio/webm",
        )
    }
    data = {
        "model": CARTESIA_STT_MODEL,
        "language": language,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CARTESIA_BASE_URL}/stt",
            headers=headers,
            files=files,
            data=data,
        )

    if resp.status_code >= 400:
        raise RuntimeError(f"Cartesia STT failed ({resp.status_code}): {resp.text[:500]}")

    body = resp.json()
    return (body.get("text") or "").strip()
