# --- Builder stage: install dependencies into a venv ---
# Why multi-stage: keeps the final runtime image free of build toolchains
# (gcc, headers) needed only to compile wheels like asyncpg/psycopg2, which
# meaningfully shrinks image size and attack surface.
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

# Non-root user: never run the app as root inside the container.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8000

# Shell form (not exec-form array) is required here so $PORT actually
# expands — Railway (and most PaaS platforms) assign a dynamic port via
# the PORT env var at container start, which an exec-form CMD can't read.
# Defaults to 8000 for docker-compose / local `docker run`, where PORT
# isn't set.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1'

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
