# syntax=docker/dockerfile:1

# ── Stage 1: build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
# Copy only the source needed for pip install
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application source (changes frequently → placed last for cache efficiency)
COPY src/ ./src/

EXPOSE 8000
CMD ["uvicorn", "rag_chatbot.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
