# ── Stage 1: Builder ─────────────────────────────────────────
# Use a full Python image to install dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed to compile Python packages
# (psycopg2, Pillow, OpenCV all need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1-mesa-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (Docker cache layer trick —
# if requirements.txt doesn't change, this layer is reused on every build)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Final image ──────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy runtime system libs (not build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project source code
COPY . .

# Collect static files (WhiteNoise will serve them)
RUN python manage.py collectstatic --noinput

# Railway sets the PORT env variable — default to 8000
ENV PORT=8000

# Gunicorn: production-grade WSGI server
# -w 2  → 2 worker processes (good for Railway free tier)
# --bind → listen on 0.0.0.0:$PORT
CMD gunicorn core.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
