FROM python:3.12-slim-bookworm

WORKDIR /app

# Patch OS packages first so known-fixed CVEs in the base image (glibc,
# openssl, etc.) don't fail the Trivy image scan in CI. Keep the apt
# cache out of the final layer.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# System deps kept minimal -- this image is for the FastAPI harness only.
# Phase 9/10 training runs on a rented GPU box directly, not in this image.
COPY pyproject.toml ./
COPY uv.lock ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "setuptools>=78.1.1" "msgpack>=1.2.1" \
    && pip install --no-cache-dir --only-binary :all: .

COPY app ./app
COPY prompts ./prompts
COPY training ./training

ENV HARNESS_MOCK_MODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --uid 1001 --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]