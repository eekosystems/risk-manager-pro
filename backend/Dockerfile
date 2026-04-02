FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies first (layer caching — only re-runs when pyproject.toml changes)
COPY pyproject.toml .
# Create minimal package structure so pip can resolve deps from pyproject.toml
RUN mkdir -p app && touch app/__init__.py && \
    pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY start.sh .

RUN sed -i 's/\r$//' start.sh && chmod +x start.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["./start.sh"]
