# Imagen ligera para Google Cloud Run.
# Construir desde la RAÍZ del repositorio (incluye data-cde para el modo demo):
#   docker build -f backend-api/Dockerfile -t gemelo-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DATA_DIR=/app/data-cde

WORKDIR /app/backend-api
COPY backend-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend-api/ .
COPY data-cde/master /app/data-cde/master
COPY data-cde/gis/edificaciones.geojson /app/data-cde/gis/edificaciones.geojson
COPY data-cde/cobie/*.csv /app/data-cde/cobie/

RUN useradd --create-home appuser
USER appuser

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
