FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency definitions first: changes to app/tests won't invalidate this layer.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install ".[dev]"

# Project files after dependency installation.
COPY alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY tests ./tests

RUN useradd --create-home --uid 10001 pais && \
    chown -R pais:pais /app

USER pais

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]