# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (excluding dev)
RUN uv sync --frozen --no-dev --no-install-project

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY frontend/ ./frontend/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
# Expose port
EXPOSE 8080

# Health check - uses unauthenticated /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8080/health', timeout=5); exit(0 if r.json().get('status')=='healthy' else 1)"

# Run the application
CMD ["python", "-m", "uvicorn", "itemwise.api:app", "--host", "0.0.0.0", "--port", "8080"]
