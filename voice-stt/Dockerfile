FROM python:3.12-slim

WORKDIR /app

# faster-whisper's CTranslate2 backend needs libgomp at runtime for CPU inference.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Bake the model into the image at build time so container startup doesn't
# depend on network access to Hugging Face — first boot would otherwise be slow.
ARG WHISPER_MODEL_SIZE=base
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL_SIZE}', device='cpu', compute_type='int8')"

EXPOSE 8000
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
