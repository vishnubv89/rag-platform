"""
Minimal text-to-speech service — wraps Piper behind a tiny HTTP API.

Internal-only: called by the main backend's /voice/speak proxy endpoint,
never exposed directly to the frontend or the public internet.
"""
import io
import os
import wave

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from piper import PiperVoice

VOICE_PATH = os.environ.get("PIPER_VOICE_PATH", "/models/voice.onnx")

app = FastAPI(title="voice-tts")

_voice: PiperVoice | None = None


class SpeakRequest(BaseModel):
    text: str


@app.on_event("startup")
async def load_voice() -> None:
    global _voice
    _voice = PiperVoice.load(VOICE_PATH)


@app.get("/health")
async def health():
    return {"status": "ok", "voice": os.path.basename(VOICE_PATH)}


@app.post("/speak")
async def speak(req: SpeakRequest):
    if _voice is None:
        raise HTTPException(status_code=503, detail="Voice model still loading")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        _voice.synthesize_wav(req.text, wav_file)

    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")
