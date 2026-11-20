"""Procesamiento GIS: Shapefile -> EPSG:4326 -> GeoJSON web.

Lee el Shapefile de edificaciones de data-cde/gis/, normaliza atributos, reproyecta a WGS84
(EPSG:4326) y escribe data-cde/gis/edificaciones.geojson, que consumen la API y load_to_db.py.

Uso:
    python etl-scripts/process_shapefiles.py                       # primer .shp de data-cde/gis
    python etl-scripts/process_shapefiles.py --shp ruta/edif.shp --id-field COD_EDIF
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd

from cde_paths import BUILDING_IDS, GEOJSON, GIS_DIR, MONITORED_IDS

KEEP = ["building_id", "name", "is_monitored", "use_type", "levels", "bays_x", "bays_y", "year_built"]
DEFAULTS = {"levels": 4, "bays_x": 3, "bays_y": 2}


def process(shp: Path, id_field: str, out: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shp)
    if gdf.crs is None:
        raise SystemExit(f"{shp.name} no tiene sistema de coordenadas (.prj). Defínalo antes de continuar.")
    print(f"Leído {shp.name}: {len(gdf)} entidades, CRS {gdf.crs.to_string()}")

    gdf = gdf.rename(columns={id_field: "building_id"}) if id_field != "building_id" else gdf
    gdf.columns = [c if c == "geometry" else c.lower() for c in gdf.columns]
    if "building_id" not in gdf.columns:
        raise SystemExit(f"No se encontró el campo de llave '{id_field}' en el Shapefile")

    gdf["building_id"] = gdf["building_id"].astype(str).str.strip().str.upper()
    unknown = set(gdf["building_id"]) - set(BUILDING_IDS)
    if unknown:
        print(f"[AVISO] building_id no reconocidos: {sorted(unknown)}")

    gdf["is_monitored"] = gdf["building_id"].isin(MONITORED_IDS)
    if "name" not in gdf.columns:
        gdf["name"] = gdf["building_id"]
    for col, default in DEFAULTS.items():
        if col not in gdf.columns:
            gdf[col] = default
    for col in ("use_type", "year_built"):
        if col not in gdf.columns:
            gdf[col] = None

    gdf = gdf[KEEP + ["geometry"]].to_crs(epsg=4326)
    gdf["geometry"] = gdf.geometry.make_valid()
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GeoJSON")
    print(f"Escrito {out} ({len(gdf)} edificaciones, EPSG:4326)")
    return gdf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shp", type=Path, help="Shapefile de entrada (por defecto el primero en data-cde/gis)")
    ap.add_argument("--id-field", default="building_id", help="Campo del SHP con el código del edificio")
    ap.add_argument("--out", type=Path, default=GEOJSON)
    args = ap.parse_args()

    shp = args.shp or next(iter(sorted(GIS_DIR.glob("*.shp"))), None)
    if shp is None:
        print("No hay archivos .shp en data-cde/gis; se conserva el GeoJSON existente.")
        return 0
    process(shp, args.id_field, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
