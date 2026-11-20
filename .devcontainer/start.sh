#!/usr/bin/env bash
# Arranca la API (puerto 8000) y el dashboard (puerto 5173) en segundo plano.
# Registros: /tmp/api.log y /tmp/dashboard.log
cd "$(dirname "$0")/.."
setsid nohup python -m uvicorn main:app --app-dir backend-api --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 < /dev/null &
cd frontend-dashboard
setsid nohup npm run dev -- --host 0.0.0.0 > /tmp/dashboard.log 2>&1 < /dev/null &
echo "Gemelo digital iniciado: dashboard en el puerto 5173, API en el 8000."
