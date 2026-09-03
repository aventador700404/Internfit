# syntax=docker/dockerfile:1

FROM python:3.12-bookworm AS builder

WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY internfit_web/requirements.txt ./requirements.txt
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim-bookworm AS runner

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1001 appuser

COPY --from=builder /wheels /wheels
COPY internfit_web/requirements.txt /tmp/requirements.txt
RUN pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -rf /wheels /tmp/requirements.txt

COPY internfit /app/internfit
COPY internfit_web /app/internfit_web

RUN chown -R appuser:appuser /app
USER appuser

ENV PORT=10000
EXPOSE 10000

CMD ["python", "internfit_web/server.py"]
