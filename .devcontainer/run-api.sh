#!/usr/bin/env bash
# API FastAPI en primer plano (puerto 8000). Se detiene con Ctrl+C.
cd "$(dirname "$0")/../backend-api"
if ! python -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "Instalando dependencias del backend..."
  pip install --no-cache-dir -r requirements.txt
fi
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
