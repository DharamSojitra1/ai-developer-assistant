FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch to minimize image size and RAM usage on Render free tier (512MB limit)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir sentence-transformers && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the cross-encoder reranker model so Render cold starts are fast and avoid network downloads
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"

COPY app ./app

RUN useradd --create-home --shell /usr/sbin/nologin appuser && \
    mkdir -p /app/chroma_db /app/state /app/.cache && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Listen on Render's dynamic $PORT or default to 8000; single worker to stay under 512MB RAM
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]