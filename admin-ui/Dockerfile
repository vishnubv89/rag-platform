FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir hatchling

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

EXPOSE 8080
CMD ["uvicorn", "admin_ui.main:app", "--host", "0.0.0.0", "--port", "8080"]
