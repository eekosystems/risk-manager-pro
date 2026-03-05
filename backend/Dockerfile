FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies first (layer caching — only re-runs when pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install \
    fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg pydantic pydantic-settings \
    structlog python-jose[cryptography] httpx azure-identity azure-search-documents \
    azure-storage-blob openai alembic tenacity python-multipart pypdf python-docx tiktoken

FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
