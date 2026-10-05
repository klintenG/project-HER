# Project HER - Cloud Run image (Flask web_ui.py served by gunicorn)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg for moviepy; fonts + libs for Pillow/moviepy text rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libfontconfig1 \
    libglib2.0-0 \
    libgl1 \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --chown=appuser:appuser . .
RUN mkdir -p output temp assets/fonts assets/music assets/sfx \
    && chown -R appuser:appuser /app
USER appuser

# Cloud Run injects $PORT (default 8080). One worker + threads keeps in-memory
# job state/SSE consistent; long timeout allows multi-minute video renders.
ENV PORT=8080
CMD exec gunicorn web_ui:app \
    --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 8 \
    --timeout 900 \
    --log-level info
