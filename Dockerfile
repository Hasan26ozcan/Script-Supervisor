FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal -- this image is for the FastAPI harness only.
# Phase 9/10 training runs on a rented GPU box directly, not in this image.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY app ./app

ENV HARNESS_MOCK_MODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
