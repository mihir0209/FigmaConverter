# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Create non-root user
RUN useradd --no-create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Copy application
COPY --chown=appuser:appuser . .

# Create data directories
RUN mkdir -p /app/data/state /app/data/assembled_projects /app/data/output \
    && chown -R appuser:appuser /app/data

USER appuser

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py"]