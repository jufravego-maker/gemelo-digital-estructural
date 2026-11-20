"""Carga el CDE en PostgreSQL + PostGIS + TimescaleDB.

Orden: buildings (GeoJSON) -> components + component_attributes (COBie) -> sensors (tabla maestra).
Es idempotente: actualiza registros existentes (UPSERT).

Uso:
    python etl-scripts/load_to_db.py --database-url postgresql://gemelo:gemelo@localhost:5432/gemelo
    (o definir la variable de entorno DATABASE_URL)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import psycopg

from cde_paths import GEOJSON, MASTER_CSV
from parse_ifc_cobie import load_cobie


def none_if_empty(v):
    return v if v not in ("", None) else None


def load(conn: psycopg.Connection) -> None:
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        for f in gj["features"]:
            p = f["properties"]
            cur.execute(
                """
                INSERT INTO buildings (building_id, name, is_monitored, use_type, levels, bays_x, bays_y,
                                       year_built, geom)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
                ON CONFLICT (building_id) DO UPDATE SET
                    name = EXCLUDED.name, is_monitored = EXCLUDED.is_monitored, use_type = EXCLUDED.use_type,
                    levels = EXCLUDED.levels, bays_x = EXCLUDED.bays_x, bays_y = EXCLUDED.bays_y,
                    year_built = EXCLUDED.year_built, geom = EXCLUDED.geom
                """,
                (p["building_id"], p.get("name"), bool(p.get("is_monitored")), p.get("use_type"),
                 p.get("levels"), p.get("bays_x"), p.get("bays_y"), p.get("year_built"),
                 json.dumps(f["geometry"])),
            )
        print(f"buildings: {len(gj['features'])}")

        comp, attr = load_cobie()
        for _, c in comp.iterrows():
            cur.execute(
                """
                INSERT INTO components (ifc_global_id, building_id, name, type_name, space, description,
                                        ext_system, ext_object, tag_number, asset_identifier, installation_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ifc_global_id) DO UPDATE SET
                    building_id = EXCLUDED.building_id, name = EXCLUDED.name, type_name = EXCLUDED.type_name,
                    space = EXCLUDED.space, description = EXCLUDED.description,
                    ext_system = EXCLUDED.ext_system, ext_object = EXCLUDED.ext_object,
                    tag_number = EXCLUDED.tag_number, asset_identifier = EXCLUDED.asset_identifier,
                    installation_date = EXCLUDED.installation_date
                """,
                (c["ifc_global_id"], c["building_id"], c["Name"], none_if_empty(c.get("TypeName")),
                 none_if_empty(c.get("Space")), none_if_empty(c.get("Description")),
                 none_if_empty(c.get("ExtSystem")), none_if_empty(c.get("ExtObject")),
                 none_if_empty(c.get("TagNumber")), none_if_empty(c.get("AssetIdentifier")),
                 none_if_empty(c.get("InstallationDate"))),
            )
        for _, a in attr.iterrows():
            cur.execute(
                """
                INSERT INTO component_attributes (ifc_global_id, name, value, unit, category, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ifc_global_id, name) DO UPDATE SET
                    value = EXCLUDED.value, unit = EXCLUDED.unit, category = EXCLUDED.category,
                    description = EXCLUDED.description
                """,
                (a["ifc_global_id"], a["Name"], none_if_empty(a.get("Value")), none_if_empty(a.get("Unit")),
                 none_if_empty(a.get("Category")), none_if_empty(a.get("Description"))),
            )
        print(f"components: {len(comp)} | component_attributes: {len(attr)}")

        with open(MASTER_CSV, newline="", encoding="utf-8") as fh:
            sensors = list(csv.DictReader(fh))
        for s in sensors:
            cur.execute(
                """
                INSERT INTO sensors (sensor_id, building_id, ifc_global_id, ifc_class, element_name, level,
                                     grid_x, grid_y, sensor_type, k_design_kn_m, modal_mass_t, installed_on)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sensor_id) DO UPDATE SET
                    building_id = EXCLUDED.building_id, ifc_global_id = EXCLUDED.ifc_global_id,
                    ifc_class = EXCLUDED.ifc_class, element_name = EXCLUDED.element_name,
                    level = EXCLUDED.level, grid_x = EXCLUDED.grid_x, grid_y = EXCLUDED.grid_y,
                    sensor_type = EXCLUDED.sensor_type, k_design_kn_m = EXCLUDED.k_design_kn_m,
                    modal_mass_t = EXCLUDED.modal_mass_t, installed_on = EXCLUDED.installed_on
                """,
                (s["sensor_id"], s["building_id"], s["ifc_global_id"], s["ifc_class"],
                 none_if_empty(s.get("element_name")), int(s["level"]), int(s["grid_x"]), int(s["grid_y"]),
                 none_if_empty(s.get("sensor_type")), float(s["k_design_kn_m"]),
                 float(s["modal_mass_t"]) if s.get("modal_mass_t") else None,
                 none_if_empty(s.get("installed_on"))),
            )
        print(f"sensors: {len(sensors)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = ap.parse_args()
    if not args.database_url:
        ap.error("Defina --database-url o la variable DATABASE_URL")
    with psycopg.connect(args.database_url) as conn:
        load(conn)
    print("Carga completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
