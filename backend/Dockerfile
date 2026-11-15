# Multi-stage production Dockerfile for PulseOps Backend on Render
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.11-slim as runner

WORKDIR /app

# Create unprivileged service user
RUN groupadd -g 1001 pulseops && \
    useradd -u 1001 -g pulseops -s /bin/sh pulseops

# Copy installed dependencies from builder
COPY --from=builder /root/.local /home/pulseops/.local
ENV PATH=/home/pulseops/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY --chown=pulseops:pulseops app/ /app/app/
COPY --chown=pulseops:pulseops seed_data.py /app/

USER pulseops

EXPOSE 8000

# Render Web Service Health Check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/healthz')" || exit 1

# Start Uvicorn production server (respects Render's dynamic $PORT env var, defaulting to 8000)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
