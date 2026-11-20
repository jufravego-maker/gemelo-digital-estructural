"""Procesamiento BIM: IFC (IfcOpenShell) + COBie (Pandas/OpenPyXL).

1. Lee las hojas COBie Component y Attribute (de .xlsx o .csv) y las vincula por GlobalId
   (Component.ExtIdentifier).
2. Para cada modelo data-cde/bim-ifc/EDIF-0X.ifc extrae la jerarquía IfcSite -> IfcBuilding ->
   IfcBuildingStorey y los elementos estructurales portantes.
3. Cruza IFC <-> COBie <-> tabla maestra y reporta GlobalId faltantes.
4. (Opcional --glb) Convierte la geometría estructural a .glb ligero con IfcConvert.

Salidas en data-cde/processed/:
    ifc_elements.csv        elementos portantes extraídos de los IFC
    components.csv          COBie Component + building_id + bandera in_ifc
    attributes.csv          COBie Attribute + ifc_global_id
    EDIF-0X.glb             (con --glb)

Uso:
    python etl-scripts/parse_ifc_cobie.py [--glb] [--strict]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from cde_paths import COBIE_DIR, IFC_DIR, MASTER_CSV, PROCESSED, building_from_space

STRUCTURAL_CLASSES = ["IfcColumn", "IfcBeam", "IfcWall", "IfcSlab", "IfcFooting", "IfcMember"]


# ---------------------------------------------------------------- COBie
def read_cobie_sheet(sheet: str, cobie_dir: Path = COBIE_DIR) -> pd.DataFrame:
    """Lee una hoja COBie desde <sheet>.csv o desde cualquier .xlsx del directorio."""
    csv_path = cobie_dir / f"{sheet}.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    for xlsx in sorted(cobie_dir.glob("*.xlsx")):
        sheets = pd.ExcelFile(xlsx, engine="openpyxl").sheet_names
        if sheet in sheets:
            return pd.read_excel(xlsx, sheet_name=sheet, dtype=str, engine="openpyxl").fillna("")
    raise FileNotFoundError(f"No se encontró la hoja COBie '{sheet}' en {cobie_dir}")


def load_cobie(cobie_dir: Path = COBIE_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    comp = read_cobie_sheet("Component", cobie_dir)
    comp = comp.rename(columns={"ExtIdentifier": "ifc_global_id"})
    comp["building_id"] = comp["Space"].map(building_from_space)

    attr = read_cobie_sheet("Attribute", cobie_dir)
    attr = attr[attr["SheetName"].str.lower() == "component"]
    attr = attr.merge(comp[["Name", "ifc_global_id"]], left_on="RowName", right_on="Name",
                      how="left", suffixes=("", "_comp")).drop(columns=["Name_comp"])
    orphan = attr["ifc_global_id"].isna().sum()
    if orphan:
        print(f"[AVISO] {orphan} atributos COBie apuntan a componentes inexistentes")
    return comp, attr.dropna(subset=["ifc_global_id"])


# ---------------------------------------------------------------- IFC
def extract_ifc(path: Path) -> pd.DataFrame:
    import ifcopenshell
    import ifcopenshell.util.element as uel

    model = ifcopenshell.open(str(path))
    building_id = path.stem.upper()
    sites = [s.Name for s in model.by_type("IfcSite")]
    buildings = [b.Name for b in model.by_type("IfcBuilding")]
    storeys = model.by_type("IfcBuildingStorey")
    print(f"{path.name} ({model.schema}): sitio={sites} edificio={buildings} niveles={len(storeys)}")

    rows = []
    for cls in STRUCTURAL_CLASSES:
        for el in model.by_type(cls):
            container = uel.get_container(el)
            storey = container if container and container.is_a("IfcBuildingStorey") else None
            rows.append({
                "building_id": building_id,
                "ifc_global_id": el.GlobalId,
                "ifc_class": el.is_a(),
                "name": el.Name,
                "storey": storey.Name if storey else None,
                "storey_elevation": getattr(storey, "Elevation", None) if storey else None,
                "load_bearing": _pset_value(uel, el, "LoadBearing"),
            })
    df = pd.DataFrame(rows)
    if not df.empty and "load_bearing" in df:
        # Conserva los portantes; si la propiedad no existe se asume portante.
        df = df[df["load_bearing"].isna() | (df["load_bearing"] == True)]  # noqa: E712
    print(f"  -> {len(df)} elementos estructurales portantes")
    return df


def _pset_value(uel, element, prop):
    for props in uel.get_psets(element).values():
        if prop in props:
            return props[prop]
    return None


def convert_glb(ifc_path: Path, out: Path) -> None:
    exe = shutil.which("IfcConvert")
    if not exe:
        print("[AVISO] IfcConvert no está en el PATH; se omite la conversión a GLB")
        return
    cmd = [exe, "-y", "--use-element-guids", str(ifc_path), str(out),
           "--include", "entities", *STRUCTURAL_CLASSES]
    subprocess.run(cmd, check=True)
    print(f"  -> {out.name}")


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glb", action="store_true", help="Generar .glb con IfcConvert")
    ap.add_argument("--strict", action="store_true", help="Fallar si hay GlobalId de la tabla maestra sin IFC")
    args = ap.parse_args()
    PROCESSED.mkdir(parents=True, exist_ok=True)

    comp, attr = load_cobie()
    master = pd.read_csv(MASTER_CSV, dtype=str)
    print(f"COBie: {len(comp)} componentes, {len(attr)} atributos | Tabla maestra: {len(master)} sensores")

    ifc_files = sorted(IFC_DIR.glob("*.ifc"))
    errors = 0
    if ifc_files:
        elements = pd.concat([extract_ifc(p) for p in ifc_files], ignore_index=True)
        elements.to_csv(PROCESSED / "ifc_elements.csv", index=False)
        ifc_ids = set(elements["ifc_global_id"])
        comp["in_ifc"] = comp["ifc_global_id"].isin(ifc_ids)

        modeled = {p.stem.upper() for p in ifc_files}
        missing = master[master["building_id"].isin(modeled) & ~master["ifc_global_id"].isin(ifc_ids)]
        for _, r in missing.iterrows():
            print(f"[ERROR] {r.sensor_id}: GlobalId {r.ifc_global_id} no existe en {r.building_id}.ifc")
        errors += len(missing)
        not_in_cobie = ifc_ids - set(comp["ifc_global_id"])
        if not_in_cobie:
            print(f"[AVISO] {len(not_in_cobie)} elementos IFC portantes sin registro COBie")
        if args.glb:
            for p in ifc_files:
                convert_glb(p, PROCESSED / f"{p.stem.upper()}.glb")
    else:
        print("No hay modelos .ifc en data-cde/bim-ifc; solo se procesa COBie.")
        comp["in_ifc"] = None

    comp.to_csv(PROCESSED / "components.csv", index=False)
    attr.to_csv(PROCESSED / "attributes.csv", index=False)
    print(f"Escrito {PROCESSED / 'components.csv'} y {PROCESSED / 'attributes.csv'}")
    return 1 if (errors and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
