FROM python:3.12-slim

WORKDIR /app

# System libs needed for psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from pyproject (no editable install yet)
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "httpx>=0.27.0" \
    "Pillow>=10.4.0" \
    "structlog>=24.2.0" \
    "celery[redis]>=5.4.0" \
    "sqlalchemy>=2.0.0" \
    "alembic>=1.13.0" \
    "asyncpg>=0.29.0" \
    "psycopg2-binary>=2.9.0" \
    "openai>=1.35.0" \
    "fpdf2>=2.8.0" \
    "boto3>=1.34.0"

# Copy source after deps are installed (better cache layering)
COPY src/ ./src/
COPY config/ ./config/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

ENV PYTHONPATH=/app/src

CMD python -m uvicorn content_agent.main:app --host 0.0.0.0 --port ${PORT:-8000}
