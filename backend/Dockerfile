# ========== BUILDER ==========
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


# ========== FINAL IMAGE ==========
FROM python:3.12-slim

# Security Best Practice: non-root user
RUN addgroup --system app && adduser --system --group app --home /home/app --shell /bin/bash


WORKDIR /home/app/web

# Install deps from wheels
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy Python source
COPY ./src ./app

# Ownership
RUN mkdir -p /home/app/.npm /home/app/.config \
    && chown -R app:app /home/app \
    && chown -R app:app /home/app/web

USER app

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers ${WORKERS}"]
