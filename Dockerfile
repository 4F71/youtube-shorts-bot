# ============================================================
# Dockerfile — YouTube Shorts Bot
# Base: Python 3.11 slim + FFmpeg + DejaVu fonts
# ============================================================

FROM python:3.11-slim

# System dependencies: FFmpeg + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create output directories
RUN mkdir -p output/audio output/visuals output/music output/final output/temp output/scripts assets/music

# Expose FastAPI port
EXPOSE 8000

# Default: run FastAPI server (triggered by n8n)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]