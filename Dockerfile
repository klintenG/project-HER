# Project HER - Cloud Run image (Flask web_ui.py served by gunicorn)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install prerequisites for NodeSource, multimedia, fonts, and headless Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends \
        nodejs \
        chromium \
        ffmpeg \
        libsm6 \
        libxext6 \
        libfontconfig1 \
        libglib2.0-0 \
        libgl1 \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        libnss3 \
        libdbus-1-3 \
        libatk1.0-0 \
        libgbm-dev \
        libasound2 \
        libxrandr2 \
        libxkbcommon-dev \
        libxfixes3 \
        libxcomposite1 \
        libxdamage1 \
        libatk-bridge2.0-0 \
        libpango-1.0-0 \
        libcairo2 \
        libcups2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
ENV HOME=/home/appuser
WORKDIR /app

# Install Python dependencies
COPY requirements.txt requirements-news.txt requirements-portfolio.txt requirements-editorial.txt ./
ARG INSTALL_NEWS_CUTOUTS=1
RUN pip install --upgrade pip && pip install -r requirements.txt -r requirements-portfolio.txt -r requirements-editorial.txt \
    && if [ "$INSTALL_NEWS_CUTOUTS" = "1" ]; then pip install -r requirements-news.txt; fi
ENV U2NET_HOME=/app/temp/news-models \
    NUMBA_CACHE_DIR=/app/temp/numba

# Pre-install Remotion npm dependencies (leverages Docker cache)
COPY remotion/package.json remotion/package-lock.json /app/remotion/
RUN cd /app/remotion && npm ci --include=dev

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure runtime directories exist with appuser permissions
RUN mkdir -p output temp assets/fonts assets/music assets/sfx \
             remotion/public/audio remotion/public/images \
             /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser

# Pre-download Remotion Chrome Headless Shell into appuser cache during build
USER appuser
RUN cd /app/remotion && npx remotion browser ensure
RUN python scripts/setup_editorial.py

# Cloud Run injects $PORT (default 8080). One worker + threads keeps in-memory
# job state/SSE consistent; long timeout allows video renders.
ENV PORT=8080
CMD exec gunicorn web_ui:app \
    --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --threads 8 \
    --timeout 900 \
    --log-level info
