"""Fase 1 — Valida las llaves maestras del gemelo digital.

Comprueba que:
  * la tabla maestra tenga sensor_id únicos, building_id válidos y GlobalId IFC bien formados;
  * solo las edificaciones monitoreadas tengan sensores;
  * cada ifc_global_id de la tabla exista en COBie (Component.ExtIdentifier) en el mismo edificio;
  * el GeoJSON tenga las 4 edificaciones con is_monitored coherente.

Solo usa la librería estándar para poder ejecutarse en CI sin dependencias.
Sale con código 1 si encuentra errores.

Uso:
    python etl-scripts/validate_master_table.py
"""
from __future__ import annotations

import csv
import json
import sys

from cde_paths import (BUILDING_IDS, COBIE_DIR, GEOJSON, MASTER_CSV, MONITORED_IDS,
                       building_from_space, is_ifc_guid)

REQUIRED_MASTER = ["sensor_id", "building_id", "ifc_global_id", "ifc_class", "level",
                   "grid_x", "grid_y", "k_design_kn_m"]
STRUCTURAL_CLASSES = {"IfcColumn", "IfcBeam", "IfcWall", "IfcSlab", "IfcFooting", "IfcMember"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    master = read_csv(MASTER_CSV)
    missing_cols = [c for c in REQUIRED_MASTER if c not in (master[0].keys() if master else [])]
    if missing_cols:
        errors.append(f"Tabla maestra: faltan columnas {missing_cols}")

    components = {}
    comp_path = COBIE_DIR / "Component.csv"
    if comp_path.exists():
        for row in read_csv(comp_path):
            gid = row.get("ExtIdentifier", "")
            if not is_ifc_guid(gid):
                errors.append(f"COBie Component '{row.get('Name')}': ExtIdentifier inválido '{gid}'")
            if gid in components:
                errors.append(f"COBie Component: ExtIdentifier duplicado {gid}")
            components[gid] = row
        names = [r["Name"] for r in components.values()]
        dup_names = {n for n in names if names.count(n) > 1}
        if dup_names:
            errors.append(f"COBie Component: Name duplicados {sorted(dup_names)}")
    else:
        warnings.append("No se encontró data-cde/cobie/Component.csv; se omite el cruce con COBie")

    seen_sensors, seen_gids = set(), set()
    for i, row in enumerate(master, start=2):
        sid, bid, gid = row["sensor_id"], row["building_id"], row["ifc_global_id"]
        where = f"Tabla maestra fila {i} ({sid})"
        if sid in seen_sensors:
            errors.append(f"{where}: sensor_id duplicado")
        seen_sensors.add(sid)
        if bid not in BUILDING_IDS:
            errors.append(f"{where}: building_id desconocido '{bid}'")
        elif bid not in MONITORED_IDS:
            errors.append(f"{where}: {bid} es la edificación de referencia y no debe tener sensores")
        if not is_ifc_guid(gid):
            errors.append(f"{where}: ifc_global_id inválido '{gid}'")
        if gid in seen_gids:
            warnings.append(f"{where}: el elemento {gid} tiene más de un sensor")
        seen_gids.add(gid)
        if row["ifc_class"] not in STRUCTURAL_CLASSES:
            errors.append(f"{where}: ifc_class '{row['ifc_class']}' no es un elemento portante")
        try:
            if float(row["k_design_kn_m"]) <= 0:
                raise ValueError
            int(row["level"]), int(row["grid_x"]), int(row["grid_y"])
        except ValueError:
            errors.append(f"{where}: valores numéricos inválidos (k_design, level, grid)")
        if components:
            comp = components.get(gid)
            if comp is None:
                errors.append(f"{where}: {gid} no existe en COBie Component.ExtIdentifier")
            else:
                if building_from_space(comp.get("Space", "")) != bid:
                    errors.append(f"{where}: COBie ubica {gid} en '{comp.get('Space')}', no en {bid}")
                if comp.get("ExtObject") and comp["ExtObject"] != row["ifc_class"]:
                    errors.append(f"{where}: clase IFC distinta en COBie ({comp['ExtObject']})")
                if comp.get("TagNumber") and comp["TagNumber"] != sid:
                    warnings.append(f"{where}: COBie TagNumber='{comp['TagNumber']}' difiere del sensor")

    for bid in MONITORED_IDS:
        if not any(r["building_id"] == bid for r in master):
            errors.append(f"La edificación monitoreada {bid} no tiene sensores en la tabla maestra")

    if GEOJSON.exists():
        gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
        props = {f["properties"].get("building_id"): f["properties"] for f in gj.get("features", [])}
        for bid in BUILDING_IDS:
            p = props.get(bid)
            if p is None:
                errors.append(f"GeoJSON: falta la edificación {bid}")
            elif bool(p.get("is_monitored")) != (bid in MONITORED_IDS):
                errors.append(f"GeoJSON: is_monitored incoherente para {bid}")
    else:
        warnings.append("No existe data-cde/gis/edificaciones.geojson (ejecute process_shapefiles.py)")

    for w in warnings:
        print(f"[AVISO] {w}")
    for e in errors:
        print(f"[ERROR] {e}")
    print(f"\nSensores: {len(master)} | Componentes COBie: {len(components)} | "
          f"Errores: {len(errors)} | Avisos: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
