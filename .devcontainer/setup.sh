#!/usr/bin/env bash
# Instala dependencias del backend y del dashboard (se ejecuta una vez al crear el Codespace).
set -euo pipefail
pip install --no-cache-dir -r backend-api/requirements-dev.txt
cd frontend-dashboard && npm install --no-fund --no-audit
