"""API del Gemelo Digital Estructural (BIM + GIS + IoT).

Ejecutar:  uvicorn main:app --reload --port 8000
Docs:      http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
import csv
import io
import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

import ai_assistant
from database import Repository, get_repository
from stiffness import DK_CRIT_PCT, DK_WARN_PCT, classify, delta_k_pct, stiffness_from_frequency, worst

UTC = timezone.utc

app = FastAPI(
    title="Gemelo Digital Estructural API",
    version="0.1.0",
    description="GIS (building_id) + BIM/COBie (ifc_global_id) + IoT (sensor_id) — rigidez estructural k.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

repo: Repository = get_repository()


# ============================================================================ servicios
def sensors_with_status(building_id: str | None = None) -> list[dict]:
    latest = repo.latest_readings()
    out = []
    for s in repo.list_sensors(building_id):
        r = latest.get(s["sensor_id"])
        dk = delta_k_pct(r["k_kn_m"], s["k_design_kn_m"]) if r else None
        out.append({
            **s,
            "last_time": r["time"].isoformat() if r else None,
            "k_kn_m": round(r["k_kn_m"], 1) if r else None,
            "delta_k_pct": round(dk, 2) if dk is not None else None,
            "status": classify(dk),
        })
    return out


def building_summaries() -> list[dict]:
    sensors = sensors_with_status()
    out = []
    for b in repo.list_buildings():
        own = [s for s in sensors if s["building_id"] == b["building_id"]]
        dks = [s["delta_k_pct"] for s in own if s["delta_k_pct"] is not None]
        status = worst([s["status"] for s in own]) if b["is_monitored"] else "referencia"
        out.append({
            **b,
            "status": status,
            "sensor_count": len(own),
            "worst_delta_k_pct": min(dks) if dks else None,
        })
    return out


def resolve_sensor_ids(building_id: str | None, sensor_id: str | None) -> list[dict]:
    sensors = repo.list_sensors(building_id)
    if sensor_id:
        sensors = [s for s in sensors if s["sensor_id"] == sensor_id]
        if not sensors:
            raise HTTPException(404, f"Sensor {sensor_id} no encontrado")
    return sensors


def auto_bucket(hours: int) -> int:
    """Agrega la serie para devolver ~400 puntos por sensor."""
    return max(5, int(hours * 60 / 400))


# ============================================================================ endpoints
@app.get("/api/health")
def health():
    return {"status": "ok", "mode": repo.mode, "version": app.version,
            "thresholds": {"warn_pct": DK_WARN_PCT, "crit_pct": DK_CRIT_PCT},
            "ai": ai_assistant.provider()}


@app.get("/api/buildings")
def buildings():
    """Huellas de las 4 edificaciones (GeoJSON, EPSG:4326) con su estado de rigidez."""
    features = []
    for b in building_summaries():
        geom = b.pop("geometry")
        features.append({"type": "Feature", "id": b["building_id"], "properties": b, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/buildings/{building_id}")
def building_detail(building_id: str):
    b = next((x for x in building_summaries() if x["building_id"] == building_id), None)
    if not b:
        raise HTTPException(404, f"Edificación {building_id} no encontrada")
    b.pop("geometry", None)
    return {"building": b,
            "sensors": sensors_with_status(building_id),
            "components": repo.list_components(building_id)}


@app.get("/api/elements/{ifc_global_id}")
def element_detail(ifc_global_id: str):
    """Metadatos COBie de un elemento estructural y, si existe, su sensor y última lectura."""
    comp = repo.get_component(ifc_global_id)
    if not comp:
        raise HTTPException(404, f"Elemento {ifc_global_id} no está registrado en COBie")
    sensor = next((s for s in sensors_with_status(comp["building_id"])
                   if s["ifc_global_id"] == ifc_global_id), None)
    return {"component": comp, "attributes": repo.get_attributes(ifc_global_id), "sensor": sensor}


@app.get("/api/stiffness/latest")
def stiffness_latest(building_id: str | None = None):
    return sensors_with_status(building_id)


@app.get("/api/stiffness")
def stiffness_series(building_id: str | None = None, sensor_id: str | None = None,
                     hours: int = Query(168, ge=1, le=24 * 365)):
    """Serie temporal de rigidez k por sensor, agregada en intervalos automáticos."""
    sensors = resolve_sensor_ids(building_id, sensor_id)
    end = datetime.now(UTC)
    bucket = auto_bucket(hours)
    rows = repo.get_series([s["sensor_id"] for s in sensors], end - timedelta(hours=hours), end, bucket)
    by_sensor: dict[str, list] = {}
    for r in rows:
        by_sensor.setdefault(r["sensor_id"], []).append(r)
    series = []
    for s in sensors:
        pts = by_sensor.get(s["sensor_id"], [])
        series.append({
            "sensor_id": s["sensor_id"], "building_id": s["building_id"],
            "ifc_global_id": s["ifc_global_id"], "element_name": s["element_name"],
            "k_design_kn_m": s["k_design_kn_m"],
            "points": [[r["time"].isoformat(), round(r["k_kn_m"], 1),
                        round(delta_k_pct(r["k_kn_m"], s["k_design_kn_m"]), 2)] for r in pts],
        })
    return {"hours": hours, "bucket_minutes": bucket, "series": series}


@app.get("/api/stiffness/export.csv")
def stiffness_csv(building_id: str | None = None, sensor_id: str | None = None,
                  hours: int = Query(168, ge=1, le=24 * 365)):
    data = stiffness_series(building_id, sensor_id, hours)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time_utc", "building_id", "sensor_id", "ifc_global_id", "k_kn_m", "k_design_kn_m",
                "delta_k_pct", "status"])
    for s in data["series"]:
        for t, k, dk in s["points"]:
            w.writerow([t, s["building_id"], s["sensor_id"], s["ifc_global_id"], k, s["k_design_kn_m"],
                        dk, classify(dk)])
    name = f"rigidez_{building_id or sensor_id or 'todas'}_{hours}h.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


class TelemetryIn(BaseModel):
    sensor_id: str
    time: datetime | None = None
    k_kn_m: float | None = Field(None, gt=0, description="Rigidez medida [kN/m]")
    frequency_hz: float | None = Field(None, gt=0, description="Frecuencia natural identificada [Hz]")

    @model_validator(mode="after")
    def one_measure(self):
        if self.k_kn_m is None and self.frequency_hz is None:
            raise ValueError("Envíe k_kn_m o frequency_hz")
        return self


@app.post("/api/telemetry", status_code=201)
def ingest(reading: TelemetryIn):
    """Ingesta de una lectura IoT. Si llega la frecuencia, k se calcula con la masa modal."""
    sensor = next((s for s in repo.list_sensors() if s["sensor_id"] == reading.sensor_id), None)
    if not sensor:
        raise HTTPException(404, f"Sensor {reading.sensor_id} no está en la tabla maestra")
    k = reading.k_kn_m
    if k is None:
        if not sensor.get("modal_mass_t"):
            raise HTTPException(422, "El sensor no tiene masa modal; envíe k_kn_m")
        k = stiffness_from_frequency(reading.frequency_hz, sensor["modal_mass_t"])
    t = reading.time or datetime.now(UTC)
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    repo.insert_reading(reading.sensor_id, t, k, reading.frequency_hz)
    dk = delta_k_pct(k, sensor["k_design_kn_m"])
    return {"sensor_id": reading.sensor_id, "time": t.isoformat(), "k_kn_m": round(k, 1),
            "delta_k_pct": round(dk, 2), "status": classify(dk)}


class SummaryIn(BaseModel):
    building_id: str | None = None


@app.post("/api/ai/summary")
async def ai_summary(req: SummaryIn):
    """Resumen ejecutivo y alertas de mantenimiento (Gemini API o reglas)."""
    buildings = building_summaries()
    for b in buildings:
        b.pop("geometry", None)
    sensors = sensors_with_status(req.building_id)
    if req.building_id:
        buildings = [b for b in buildings if b["building_id"] == req.building_id]
        if not buildings:
            raise HTTPException(404, f"Edificación {req.building_id} no encontrada")
    flagged = [s for s in sensors if s["status"] in ("alerta", "critico")]
    cobie = {s["ifc_global_id"]: repo.get_attributes(s["ifc_global_id"]) for s in flagged}
    return await ai_assistant.summarize(buildings, sensors, cobie)


@app.websocket("/ws/stiffness")
async def ws_stiffness(ws: WebSocket):
    """Envía periódicamente la última lectura de cada sensor y el estado de cada edificio."""
    await ws.accept()
    interval = float(os.getenv("WS_INTERVAL_S", "5"))

    async def sender():
        while True:
            buildings = {b["building_id"]: b["status"] for b in building_summaries()}
            await ws.send_json({"type": "snapshot", "time": datetime.now(UTC).isoformat(),
                                "buildings": buildings, "sensors": sensors_with_status()})
            await asyncio.sleep(interval)

    task = asyncio.create_task(sender())
    try:
        # Escucha al cliente solo para detectar la desconexión
        while not task.done():
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        task.cancel()
