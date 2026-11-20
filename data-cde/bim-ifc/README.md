# Modelos IFC estructurales

Ubicar aquí un modelo IFC (IFC2x3 o IFC4) por edificación, nombrado con su `building_id`:

```
EDIF-01.ifc
EDIF-02.ifc
EDIF-03.ifc
EDIF-04.ifc
```

Los archivos `.ifc` se versionan con **Git LFS**. Antes del primer `git add`:

```powershell
git lfs install
```

El script `etl-scripts/parse_ifc_cobie.py` extrae la jerarquía `IfcSite → IfcBuilding → IfcBuildingStorey`,
filtra los elementos portantes (`IfcColumn`, `IfcBeam`, `IfcWall`, `IfcSlab`, `IfcFooting`, `IfcMember`)
y verifica que los GlobalId de la tabla maestra existan en el modelo. Con `--glb` genera además una
versión ligera `.glb` para el navegador (requiere `IfcConvert` en el PATH).
