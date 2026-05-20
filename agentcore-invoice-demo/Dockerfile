FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Copy application code
COPY . .

EXPOSE 8080

# opentelemetry-instrument enables ADOT auto-instrumentation for FastAPI/boto3.
# AgentCore injects OTEL env vars (endpoint, service name, etc.) at runtime.
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "entrypoint:app", "--host", "0.0.0.0", "--port", "8080"]
