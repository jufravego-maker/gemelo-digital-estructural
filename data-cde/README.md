# data-cde — Entorno Común de Datos (ISO 19650)

Contenedores de información del gemelo digital. Los archivos pesados (`.ifc`, `.shp`, `.dbf`, `.shx`,
`.xlsx`, `.glb`) se gestionan con **Git LFS** (ver `.gitattributes` en la raíz).

| Carpeta | Contenido | Llave |
|---------|-----------|-------|
| `master/` | `tabla_maestra_sensores.csv`: une sensor ↔ elemento IFC ↔ edificio | `sensor_id`, `ifc_global_id`, `building_id` |
| `gis/` | Shapefile de las 4 edificaciones y su versión web `edificaciones.geojson` (EPSG:4326) | `building_id` |
| `bim-ifc/` | Modelos estructurales IFC, uno por edificio (`EDIF-01.ifc` …) | `GlobalId` |
| `cobie/` | Hojas COBie `Component` y `Attribute` (`.csv` o `.xlsx`) | `ExtIdentifier` = `GlobalId` |
| `processed/` | Salidas de los ETL (se regenera; no se versiona) | — |

## Convenciones

- **`building_id`**: `EDIF-01` … `EDIF-04`. EDIF-04 es la edificación de referencia (`is_monitored = false`).
- **`ifc_global_id`**: GlobalId IFC de 22 caracteres (alfabeto `0-9 A-Z a-z _ $`).
- **COBie `Component.Name`**: único en todo el CDE; se antepone el código del edificio (`E01-C-A1-N1`).
- **COBie `Component.Space`**: `<building_id>-N<nivel>` (ej. `EDIF-02-N4`); de ahí se deriva el edificio.
- **COBie `Component.TagNumber`**: `sensor_id` instalado en el elemento (vacío si no está instrumentado).
- **Tabla maestra**: `level` es el nivel (1 = primer piso); `grid_x`, `grid_y` son índices de eje
  (0 = eje A / eje 1). En vigas y muros indican el nudo inicial y el elemento corre en dirección X.
- **Shapefile GIS**: atributos mínimos `building_id`, `name`, `is_monitored`, `levels`, `bays_x`, `bays_y`.

> Los datos actuales son **de ejemplo** (coordenadas y GlobalId ficticios).
