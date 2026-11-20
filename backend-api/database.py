"""Acceso a datos del gemelo digital.

Dos implementaciones con la misma interfaz:
  * PostgresRepository: PostgreSQL + PostGIS + TimescaleDB (cuando existe DATABASE_URL).
  * DemoRepository: lee los archivos de data-cde/ y genera telemetría sintética determinista,
    para desarrollar y demostrar el dashboard sin base de datos.
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import threading
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

UTC = timezone.utc


class Repository(Protocol):
    mode: str

    def list_buildings(self) -> list[dict]: ...
    def list_sensors(self, building_id: str | None = None) -> list[dict]: ...
    def list_components(self, building_id: str) -> list[dict]: ...
    def get_component(self, ifc_global_id: str) -> dict | None: ...
    def get_attributes(self, ifc_global_id: str) -> list[dict]: ...
    def latest_readings(self) -> dict[str, dict]: ...
    def get_series(self, sensor_ids: list[str], start: datetime, end: datetime,
                   bucket_minutes: int) -> list[dict]: ...
    def insert_reading(self, sensor_id: str, time: datetime, k_kn_m: float,
                       frequency_hz: float | None) -> None: ...


# ============================================================================ Demo
class DemoRepository:
    """Repositorio en memoria a partir de data-cde/ con telemetría sintética.

    Escenario de demostración (Δk final tras una degradación lineal de 60 días):
      S-E02-02 ≈ -8 % (alerta), S-E03-01 ≈ -19 % (crítico), S-E03-03 ≈ -7 % (alerta).
    """

    mode = "demo"
    DRIFT = {"S-E02-02": -0.08, "S-E03-01": -0.19, "S-E03-03": -0.065}
    DEFAULT_DRIFT = -0.008
    RAMP_DAYS = 60

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        gj = json.loads((self.data_dir / "gis" / "edificaciones.geojson").read_text(encoding="utf-8"))
        self._buildings = [{**f["properties"], "geometry": f["geometry"]} for f in gj["features"]]
        self._sensors = [self._parse_sensor(r) for r in self._read_csv("master/tabla_maestra_sensores.csv")]
        self._components = {}
        for c in self._read_csv("cobie/Component.csv"):
            gid = c["ExtIdentifier"]
            self._components[gid] = {
                "ifc_global_id": gid,
                "building_id": "-".join(c["Space"].split("-")[:2]),
                "name": c["Name"], "type_name": c["TypeName"], "space": c["Space"],
                "description": c["Description"], "ext_system": c["ExtSystem"],
                "ext_object": c["ExtObject"], "tag_number": c["TagNumber"] or None,
                "asset_identifier": c["AssetIdentifier"], "installation_date": c["InstallationDate"],
            }
        by_name = {c["name"]: gid for gid, c in self._components.items()}
        self._attributes: dict[str, list[dict]] = {}
        for a in self._read_csv("cobie/Attribute.csv"):
            gid = by_name.get(a["RowName"])
            if gid and a["SheetName"].lower() == "component":
                self._attributes.setdefault(gid, []).append({
                    "name": a["Name"], "value": a["Value"], "unit": a["Unit"] or None,
                    "category": a["Category"] or None, "description": a["Description"] or None,
                })
        self._anchor = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        self._ingested: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def _read_csv(self, rel: str) -> list[dict]:
        with open(self.data_dir / rel, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _parse_sensor(r: dict) -> dict:
        return {
            "sensor_id": r["sensor_id"], "building_id": r["building_id"],
            "ifc_global_id": r["ifc_global_id"], "ifc_class": r["ifc_class"],
            "element_name": r["element_name"], "level": int(r["level"]),
            "grid_x": int(r["grid_x"]), "grid_y": int(r["grid_y"]),
            "sensor_type": r["sensor_type"], "k_design_kn_m": float(r["k_design_kn_m"]),
            "modal_mass_t": float(r["modal_mass_t"]) if r.get("modal_mass_t") else None,
            "installed_on": r.get("installed_on") or None,
        }

    # ---- catálogos
    def list_buildings(self) -> list[dict]:
        return [dict(b) for b in self._buildings]

    def list_sensors(self, building_id: str | None = None) -> list[dict]:
        return [dict(s) for s in self._sensors if building_id in (None, s["building_id"])]

    def list_components(self, building_id: str) -> list[dict]:
        return [dict(c) for c in self._components.values() if c["building_id"] == building_id]

    def get_component(self, ifc_global_id: str) -> dict | None:
        c = self._components.get(ifc_global_id)
        return dict(c) if c else None

    def get_attributes(self, ifc_global_id: str) -> list[dict]:
        return list(self._attributes.get(ifc_global_id, []))

    # ---- telemetría sintética
    def _synthetic_k(self, sensor: dict, t: datetime) -> float:
        k0 = sensor["k_design_kn_m"]
        drift = self.DRIFT.get(sensor["sensor_id"], self.DEFAULT_DRIFT)
        days_before_anchor = (self._anchor - t).total_seconds() / 86400
        progress = min(1.0, max(0.0, 1 - days_before_anchor / self.RAMP_DAYS))
        hour = t.hour + t.minute / 60
        thermal = 0.006 * math.sin(2 * math.pi * (hour - 15) / 24)  # efecto térmico diario
        seed = zlib.crc32(f"{sensor['sensor_id']}:{int(t.timestamp()) // 300}".encode())
        noise = random.Random(seed).gauss(0, 0.004)
        return k0 * (1 + drift * progress + thermal + noise)

    def _sensor(self, sensor_id: str) -> dict | None:
        return next((s for s in self._sensors if s["sensor_id"] == sensor_id), None)

    def latest_readings(self) -> dict[str, dict]:
        now = datetime.now(UTC)
        out = {}
        for s in self._sensors:
            ingested = self._ingested.get(s["sensor_id"])
            if ingested and ingested[-1]["time"] > now - timedelta(minutes=30):
                out[s["sensor_id"]] = dict(ingested[-1])
            else:
                out[s["sensor_id"]] = {"time": now, "k_kn_m": self._synthetic_k(s, now), "frequency_hz": None}
        return out

    def get_series(self, sensor_ids, start, end, bucket_minutes):
        step = timedelta(minutes=max(1, bucket_minutes))
        out = []
        for sid in sensor_ids:
            s = self._sensor(sid)
            if not s:
                continue
            t = start
            while t <= end:
                out.append({"time": t, "sensor_id": sid, "k_kn_m": self._synthetic_k(s, t)})
                t += step
            out.extend({"time": r["time"], "sensor_id": sid, "k_kn_m": r["k_kn_m"]}
                       for r in self._ingested.get(sid, []) if start <= r["time"] <= end)
        out.sort(key=lambda r: (r["sensor_id"], r["time"]))
        return out

    def insert_reading(self, sensor_id, time, k_kn_m, frequency_hz):
        with self._lock:
            buf = self._ingested.setdefault(sensor_id, [])
            buf.append({"time": time, "k_kn_m": k_kn_m, "frequency_hz": frequency_hz})
            buf.sort(key=lambda r: r["time"])
            del buf[:-5000]


# ============================================================================ PostgreSQL
class PostgresRepository:
    mode = "postgres"

    def __init__(self, dsn: str):
        import psycopg  # noqa: F401 — falla temprano si falta el driver
        self.dsn = dsn

    def _query(self, sql: str, params=()) -> list[dict]:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return conn.execute(sql, params).fetchall()

    def list_buildings(self):
        rows = self._query(
            """SELECT building_id, name, is_monitored, use_type, levels, bays_x, bays_y, year_built,
                      ST_AsGeoJSON(geom)::json AS geometry
               FROM buildings ORDER BY building_id""")
        return rows

    def list_sensors(self, building_id=None):
        sql = "SELECT * FROM sensors"
        params: tuple = ()
        if building_id:
            sql += " WHERE building_id = %s"
            params = (building_id,)
        rows = self._query(sql + " ORDER BY sensor_id", params)
        for r in rows:
            if r.get("installed_on"):
                r["installed_on"] = r["installed_on"].isoformat()
        return rows

    def list_components(self, building_id):
        return [self._fmt_component(r) for r in self._query(
            "SELECT * FROM components WHERE building_id = %s ORDER BY name", (building_id,))]

    def get_component(self, ifc_global_id):
        rows = self._query("SELECT * FROM components WHERE ifc_global_id = %s", (ifc_global_id,))
        return self._fmt_component(rows[0]) if rows else None

    @staticmethod
    def _fmt_component(r):
        if r.get("installation_date"):
            r["installation_date"] = r["installation_date"].isoformat()
        r["ifc_global_id"] = r["ifc_global_id"].strip()
        return r

    def get_attributes(self, ifc_global_id):
        return self._query(
            """SELECT name, value, unit, category, description FROM component_attributes
               WHERE ifc_global_id = %s ORDER BY category, name""", (ifc_global_id,))

    def latest_readings(self):
        rows = self._query(
            """SELECT DISTINCT ON (sensor_id) sensor_id, time, k_kn_m, frequency_hz
               FROM stiffness_readings
               WHERE time > now() - interval '7 days'
               ORDER BY sensor_id, time DESC""")
        return {r.pop("sensor_id"): r for r in rows}

    def get_series(self, sensor_ids, start, end, bucket_minutes):
        if not sensor_ids:
            return []
        return self._query(
            """SELECT time_bucket(make_interval(mins => %s), time) AS time, sensor_id,
                      avg(k_kn_m) AS k_kn_m
               FROM stiffness_readings
               WHERE sensor_id = ANY(%s) AND time BETWEEN %s AND %s
               GROUP BY 1, 2 ORDER BY 2, 1""",
            (max(1, bucket_minutes), list(sensor_ids), start, end))

    def insert_reading(self, sensor_id, time, k_kn_m, frequency_hz):
        import psycopg
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """INSERT INTO stiffness_readings (time, sensor_id, k_kn_m, frequency_hz)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (sensor_id, time) DO UPDATE
                   SET k_kn_m = EXCLUDED.k_kn_m, frequency_hz = EXCLUDED.frequency_hz""",
                (time, sensor_id, k_kn_m, frequency_hz))


# ============================================================================ factory
def default_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data-cde"))


def get_repository() -> Repository:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return PostgresRepository(dsn)
    return DemoRepository(default_data_dir())
