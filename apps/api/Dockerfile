# Stage 1: Build wheels
FROM python:3.11-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir hatchling build

# Copy tax-engine package (changes less often -> better layer caching)
COPY packages/tax-engine/ /build/tax-engine/
RUN pip wheel --no-deps --wheel-dir /build/wheels /build/tax-engine/

# Copy API source
COPY apps/api/ /build/api/
RUN pip wheel --no-deps --wheel-dir /build/wheels /build/api/

# Install all dependencies
RUN pip install --no-cache-dir --prefix=/install /build/wheels/*.whl
RUN pip install --no-cache-dir --prefix=/install fastapi "uvicorn[standard]" asyncpg "sqlalchemy[asyncio]" alembic pydantic-settings pgvector

# Stage 2: Runtime
FROM python:3.11-slim

RUN groupadd -r kara && useradd -r -g kara kara

COPY --from=builder /install /usr/local

WORKDIR /app

COPY apps/api/alembic.ini /app/
COPY apps/api/alembic/ /app/alembic/

USER kara

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn kara_api.main:app --host 0.0.0.0 --port 8000"]
