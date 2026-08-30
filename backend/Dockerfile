# L-11: digest-pin the base image. Tag resolved 2026-06-02; refresh via Dependabot.
FROM python:3.14-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97 AS builder

WORKDIR /build

# Install dependencies first (layer caching — only re-runs when pyproject.toml changes)
COPY pyproject.toml .
# Create minimal package structure so pip can resolve deps from pyproject.toml
RUN mkdir -p app && touch app/__init__.py && \
    pip install --no-cache-dir --prefix=/install .

FROM python:3.14-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97

# L-11: OCI metadata for image traceability, paired with the digest-pinned base.
LABEL org.opencontainers.image.title="risk-manager-pro-api" \
      org.opencontainers.image.vendor="Faith Group, LLC" \
      org.opencontainers.image.description="Risk Manager Pro FastAPI backend"

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
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["./start.sh"]
