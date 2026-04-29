# syntax=docker/dockerfile:1
# ============================================================================
# SEC Filing RAG — Container image
# ============================================================================

FROM python:3.11-slim AS base

# System deps for unstructured + lxml + faiss
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt-dev \
        poppler-utils \
        tesseract-ocr \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/sample_filings/ ./data/sample_filings/
COPY .env.example ./.env.example

EXPOSE 8000 8501

# Default command runs the FastAPI server.
# Override with: docker run sec-rag streamlit run app/ui.py
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
