# Gemelo Digital Estructural (BIM + GIS + IoT)

Gemelo digital de **cuatro edificaciones** integradas en un entorno geoespacial. Tres de ellas
(EDIF-01, EDIF-02, EDIF-03) tienen **monitoreo activo de rigidez estructural (k)** y EDIF-04 funciona
como **edificación de referencia (línea base)**.

La arquitectura sigue principios de **Open Data** y gestión de la información según **ISO 19650**,
con herramientas Open Source, control de versiones en GitHub y despliegue en Google Cloud.

> **Estado: v0.1 (versión inicial).** Funciona de punta a punta en *modo demo* con datos de ejemplo
> (huellas GIS, tabla maestra de sensores, hojas COBie y telemetría sintética). Los scripts ETL para
> Shapefile, IFC y COBie reales están listos para usarse cuando se carguen los archivos del proyecto.

## Probar sin instalar nada

[![Abrir en GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jufravego-maker/gemelo-digital-estructural?quickstart=1)

1. Inicie sesión en GitHub (cuenta gratuita) y haga clic en el botón de arriba → **Create codespace**.
2. Espere 2–4 minutos la primera vez (instala dependencias automáticamente).
3. La API y el dashboard arrancan solos en dos terminales (`api` y `dashboard`). Cuando la terminal
   `dashboard` muestre `Local: http://localhost:5173/`, abra la pestaña **Puertos** (Ports) y haga
   clic en el globo 🌐 del puerto **5173**.

Si el puerto 5173 responde *HTTP 502*, el dashboard no está corriendo. Arránquelo en una terminal nueva:

```bash
bash .devcontainer/run-api.sh &
bash .devcontainer/run-dashboard.sh
```

> Cuando termine, detenga el Codespace en <https://github.com/codespaces> para no consumir horas
> (el plan gratuito incluye unas 60 h/mes).

---

## Modelo de interoperabilidad (AIM federado)

| # | Dominio | Fuente de datos | Llave de vinculación | Rol en el gemelo |
|---|---------|-----------------|----------------------|------------------|
| 1 | GIS | Shapefile (`.shp`) | `building_id` (EDIF-01…EDIF-04) | Contexto territorial y estado de monitoreo (`is_monitored`) |
| 2 | BIM (geometría) | IFC (ISO 16739) | `ifc_global_id` (GlobalId, 22 caracteres) | Modelo 3D estructural y mapa de calor por rigidez |
| 3 | BIM (datos) | COBie (`.xlsx` / `.csv`) | `ExtIdentifier` (= `ifc_global_id`) y `AssetIdentifier` | Metadatos de operación y ubicación lógica de sensores |
| 4 | IoT | Telemetría (JSON / MQTT) | `sensor_id` → `ifc_global_id` | Medición continua de rigidez (k, kN/m) |

La **tabla maestra** [`data-cde/master/tabla_maestra_sensores.csv`](data-cde/master/tabla_maestra_sensores.csv)
une las tres llaves: `sensor_id ↔ ifc_global_id ↔ building_id`.

### Semáforo de rigidez

Δk = (k_medida − k_diseño) / k_diseño × 100

| Estado | Criterio (por defecto) | Color |
|--------|------------------------|-------|
| Óptimo | Δk > −5 % | Verde |
| Alerta (degradación leve) | −15 % < Δk ≤ −5 % | Amarillo |
| Crítico (pérdida de rigidez) | Δk ≤ −15 % | Rojo |

Los umbrales se ajustan con las variables `DK_WARN_PCT` y `DK_CRIT_PCT`.

---

## Estructura del repositorio

```
gemelo-digital-estructural/
├── .github/workflows/
│   ├── etl-bim-gis-pipeline.yml   # Valida y procesa IFC/COBie/SHP al hacer push
│   ├── ci.yml                     # Pruebas del backend y build del frontend
│   └── deploy-cloud-run.yml       # Despliegue manual a Cloud Run (Fase 4)
├── data-cde/                      # Contenedores de información (ISO 19650)
│   ├── master/                    # Tabla maestra sensor ↔ GlobalId ↔ edificio
│   ├── gis/                       # Shapefiles (+ GeoJSON web)
│   ├── bim-ifc/                   # Modelos .ifc (Git LFS)
│   ├── cobie/                     # Entregables COBie (Component, Attribute)
│   └── processed/                 # Salidas de los ETL (se regenera)
├── etl-scripts/                   # Python Open Source
│   ├── validate_master_table.py   # Fase 1: valida llaves y cruces
│   ├── process_shapefiles.py      # SHP → EPSG:4326 → GeoJSON
│   ├── parse_ifc_cobie.py         # IFC (IfcOpenShell) + COBie → elementos
│   ├── stiffness_calculator.py    # Señal → frecuencia → k y Δk
│   ├── iot_gateway.py             # Simulador de sensores y puente MQTT → API
│   └── load_to_db.py              # Carga PostGIS + TimescaleDB
├── db/init/01_schema.sql          # Esquema PostgreSQL + PostGIS + TimescaleDB
├── backend-api/                   # FastAPI (Cloud Run)
├── frontend-dashboard/            # React + Tailwind + MapLibre + three.js + ECharts
├── docs/                          # Documento de arquitectura e infografía
├── infra/mosquitto/               # Configuración del broker MQTT
└── docker-compose.yml             # Entorno local completo
```

---

## Puesta en marcha

### Requisitos

- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 20 LTS+](https://nodejs.org/)
- Git + [Git LFS](https://git-lfs.com/)
- (Opcional) [Docker Desktop](https://www.docker.com/products/docker-desktop/) para la base de datos y MQTT

### 1. Backend en modo demo (sin base de datos)

```powershell
cd backend-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Documentación interactiva de la API: <http://localhost:8000/docs>

### 2. Dashboard

```powershell
cd frontend-dashboard
npm install
npm run dev
```

Abrir <http://localhost:5173>. Vite redirige `/api` y `/ws` al backend en el puerto 8000.

### 3. Entorno completo con base de datos (Docker)

```powershell
docker compose up -d db mosquitto
pip install -r etl-scripts/requirements.txt
python etl-scripts/validate_master_table.py
python etl-scripts/load_to_db.py --database-url postgresql://gemelo:gemelo@localhost:5432/gemelo
$env:DATABASE_URL = "postgresql://gemelo:gemelo@localhost:5432/gemelo"
cd backend-api; uvicorn main:app --reload --port 8000
```

Simular sensores enviando lecturas a la API:

```powershell
python etl-scripts/iot_gateway.py simulate --api http://localhost:8000 --interval 5
```

### 4. Pruebas

```powershell
cd backend-api
pip install -r requirements-dev.txt
pytest
```

---

## API principal

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del servicio y modo (demo / base de datos) |
| GET | `/api/buildings` | GeoJSON de las 4 edificaciones con estado de rigidez |
| GET | `/api/buildings/{building_id}` | Edificio, sensores con última lectura y componentes COBie |
| GET | `/api/elements/{ifc_global_id}` | Metadatos COBie de un elemento + sensor asociado |
| GET | `/api/stiffness` | Serie temporal de k (filtros: `building_id`, `sensor_id`, `hours`) |
| GET | `/api/stiffness/export.csv` | Descarga CSV de la serie |
| GET | `/api/stiffness/latest` | Última lectura de cada sensor |
| POST | `/api/telemetry` | Ingesta de lectura (`k_kn_m` o `frequency_hz`) |
| POST | `/api/ai/summary` | Resumen ejecutivo (Gemini API si hay `GEMINI_API_KEY`; si no, por reglas) |
| WS | `/ws/stiffness` | Lecturas en tiempo real |

---

## Variables de entorno (backend)

| Variable | Descripción | Por defecto |
|----------|-------------|-------------|
| `DATABASE_URL` | Conexión PostgreSQL. Si no se define, se usa el modo demo | — |
| `DATA_DIR` | Carpeta `data-cde` para el modo demo | `../data-cde` |
| `DK_WARN_PCT` / `DK_CRIT_PCT` | Umbrales de alerta y crítico de Δk (%) | `-5` / `-15` |
| `GEMINI_API_KEY` | Clave de Gemini API (opcional) | — |
| `GEMINI_MODEL` | Modelo de Gemini | `gemini-2.5-flash` |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma | `*` |

---

## Plan de implementación

- [x] **v0.1** — Estructura del repositorio, datos de ejemplo, ETL, API en modo demo y dashboard.
- [ ] **Fase 1 — Llaves maestras (semana 1):** reemplazar los datos de ejemplo por los GlobalId reales
      de los 4 modelos IFC y sus COBie; completar la tabla maestra.
- [ ] **Fase 2 — Repositorio y ETL (semana 2):** subir SHP/IFC/COBie con Git LFS y poblar
      PostgreSQL + PostGIS + TimescaleDB.
- [ ] **Fase 3 — Dashboard (semanas 3–4):** cargar la geometría IFC real (That Open Engine / GLB) en
      el visor 3D, que hoy usa un pórtico paramétrico.
- [ ] **Fase 4 — Despliegue (semana 5):** Cloud Run (backend) y Firebase Hosting (frontend).

## Notas de la versión de ejemplo

- Las coordenadas de las edificaciones y los GlobalId de `data-cde/` son **ficticios** y sirven solo
  para probar el flujo completo. Deben sustituirse por los del proyecto real.
- El visor 3D construye un pórtico paramétrico a partir de niveles y vanos de cada edificio y ubica
  los elementos instrumentados según su nivel y eje (`level`, `grid_x`, `grid_y`).
