"""Rutas comunes del Entorno Común de Datos (CDE)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDE = ROOT / "data-cde"
MASTER_CSV = CDE / "master" / "tabla_maestra_sensores.csv"
GIS_DIR = CDE / "gis"
GEOJSON = GIS_DIR / "edificaciones.geojson"
IFC_DIR = CDE / "bim-ifc"
COBIE_DIR = CDE / "cobie"
PROCESSED = CDE / "processed"

BUILDING_IDS = ("EDIF-01", "EDIF-02", "EDIF-03", "EDIF-04")
MONITORED_IDS = ("EDIF-01", "EDIF-02", "EDIF-03")

# Alfabeto de GlobalId IFC (base64 comprimido de 22 caracteres)
IFC_GUID_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$")


def is_ifc_guid(value: str) -> bool:
    return isinstance(value, str) and len(value) == 22 and set(value) <= IFC_GUID_CHARS and value[0] in "0123"


def building_from_space(space: str) -> str | None:
    """'EDIF-02-N4' -> 'EDIF-02'."""
    if not space:
        return None
    parts = space.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else None
