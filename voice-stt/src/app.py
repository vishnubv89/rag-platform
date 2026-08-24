"""
Minimal speech-to-text service — wraps faster-whisper behind a tiny HTTP API.

Internal-only: called by the main backend's /voice/transcribe proxy endpoint,
never exposed directly to the frontend or the public internet.
"""
import os
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile, File
from faster_whisper import WhisperModel

MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
# int8 keeps memory/CPU load low; still accurate enough for short chat utterances.
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

app = FastAPI(title="voice-stt")

_model: WhisperModel | None = None


@app.on_event("startup")
async def load_model() -> None:
    global _model
    _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE)


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_SIZE}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model still loading")

    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        segments, info = _model.transcribe(tmp_path, beam_size=5)
        text = "".join(segment.text for segment in segments).strip()
    finally:
        os.unlink(tmp_path)

    return {"text": text, "language": info.language}
