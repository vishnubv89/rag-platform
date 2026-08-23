FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Bake a default English voice into the image so container startup doesn't
# depend on network access. Swap the URL to use a different Piper voice —
# see https://github.com/rhasspy/piper/blob/master/VOICES.md for the catalog.
ARG PIPER_VOICE=en_US-lessac-medium
RUN mkdir -p /models && \
    curl -sL -o /models/voice.onnx \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/${PIPER_VOICE}.onnx" && \
    curl -sL -o /models/voice.onnx.json \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/${PIPER_VOICE}.onnx.json"

ENV PIPER_VOICE_PATH=/models/voice.onnx

EXPOSE 8000
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
