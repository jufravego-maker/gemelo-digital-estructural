#!/usr/bin/env bash
# Dashboard Vite en primer plano (puerto 5173). Se detiene con Ctrl+C.
cd "$(dirname "$0")/../frontend-dashboard"
if [ ! -d node_modules ]; then
  echo "Instalando dependencias del dashboard..."
  npm install --no-fund --no-audit
fi
exec npm run dev -- --host 0.0.0.0
