FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PREDICTOR_CACHE_DIR=/app/cache

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/cache \
    && chown -R appuser:appuser /app

COPY predictor/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY predictor/app.py /app/app.py

USER appuser

CMD ["python", "/app/app.py"]
