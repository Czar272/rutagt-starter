# Versionado de datasets

| Campo         | Valor                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------- |
| Ticket        | RGT-32                                                                                      |
| Decisión      | [ADR-0032](../architecture/adr/0032-versionado-de-datasets-con-snapshots-inmutables.md)     |
| Complementa a | [ADR-0004](../architecture/adr/0004-capas-de-datos-inmutables-con-procedencia.md)           |
| Implementa    | RGT-33 (snapshots crudos) · Sprint 6 (capas derivadas) · Sprint 8 (versiones publicadas)    |

Define cómo se nombran, escriben y conservan las versiones de los datos en cada capa del pipeline, para que cualquier feed publicado pueda rastrearse hasta la descarga exacta de la que proviene.

## 1. Flujo

```text
fuente ──fetch──► raw/<snapshot_id>/ ──normalizar──► normalized/<snapshot_id>/ ──exportar──► gtfs/<snapshot_id>/ ──validar y publicar──► published/<feed_version>/
                  inmutable                         regenerable                              regenerable                              inmutable
```

| Paso      | Entrada                              | Salida                       | Registra                                          |
| --------- | ------------------------------------ | ---------------------------- | ------------------------------------------------- |
| Recolectar | Configuración de fuentes            | Snapshot crudo               | `run_manifest.json`, `.provenance.json` por archivo |
| Normalizar | Snapshot (por defecto, `LATEST`)    | Capa `staging` o `normalized` | Snapshot, SHA-256 de entradas, commit, correcciones |
| Exportar  | Capa normalizada o base canónica     | Feed GTFS de trabajo         | Lo anterior más el conteo por archivo GTFS         |
| Publicar  | Feed GTFS validado                   | Versión publicada            | `release.json`                                     |

Cada paso lee una versión explícita de la capa anterior; nunca «lo que haya en la carpeta».

## 2. Nombres

| Elemento         | Formato                | Ejemplo                    | Regla                                                                 |
| ---------------- | ---------------------- | -------------------------- | --------------------------------------------------------------------- |
| Snapshot crudo   | `AAAAMMDDTHHMMSSZ`     | `20261126T174500Z`         | Hora UTC de inicio de la ejecución (ISO 8601 básico)                 |
| Ejecución        | `run_id` (UUID hex)    | `3f2a…`                    | Correlaciona logs; se guarda en el manifiesto                         |
| Versión de feed  | `AAAA.MM.DD.N`         | `2026.12.15.1`             | Fecha de publicación en `America/Guatemala`; `N` empieza en 1 cada día |
| Archivo del feed | `rutagt-gtfs-<versión>.zip` | `rutagt-gtfs-2026.12.15.1.zip` | Mismo valor que `feed_info.feed_version`                        |
| Fuente           | `<publicador>_<conjunto>[_<año>]` | `muniguate_tubus_stops_2025` | Una capa nueva del publicador es una fuente nueva            |

Las versiones de feed se ordenan por fecha y luego por `N` como número (`2026.12.15.10` es posterior a `2026.12.15.9`).

## 3. Estructura de directorios

```text
data/
├── raw/
│   ├── LATEST                              # «20261126T174500Z»: último snapshot completo
│   ├── 20260822T201200Z/
│   │   ├── run_manifest.json
│   │   └── muniguate/
│   │       ├── tubus_stops_2025.geojson
│   │       └── tubus_stops_2025.geojson.provenance.json
│   └── 20261126T174500Z/
│       └── …
├── staging/<snapshot_id>/…
├── normalized/<snapshot_id>/…
├── gtfs/<snapshot_id>/…
└── published/
    └── 2026.12.15.1/
        ├── rutagt-gtfs-2026.12.15.1.zip
        ├── release.json
        └── validation-report.json
```

## 4. Reglas por capa

### Crudos (`raw`)

- El recolector crea el directorio del snapshot de forma exclusiva y falla si ya existe.
- Ningún proceso modifica ni borra archivos de un snapshot terminado.
- Si alguna fuente falla, el snapshot se conserva, pero `LATEST` no cambia.
- `LATEST` se escribe al final, después del manifiesto, para que nunca apunte a un snapshot a medias.
- Cada snapshot guarda copia completa de lo descargado, aunque no haya cambiado. Si el total supera 1 GB se evaluará deduplicar por SHA-256 (ADR-0032).

### Derivadas (`staging`, `normalized`, `gtfs`)

- Se nombran por el snapshot de origen y se pueden borrar y regenerar en cualquier momento.
- Una reconstrucción escribe en un directorio temporal y lo renombra al terminar, para que no quede un resultado mezclado.
- La procedencia de cada salida declara:
  - `snapshot_id` y SHA-256 de cada archivo de entrada;
  - `code_version`: commit de Git del código que la produjo;
  - `corrections_version`: commit de las correcciones manuales aplicadas;
  - fecha UTC, conteos y advertencias, como en la capa cruda.

### Publicadas (`published`)

- Una versión publicada nunca se modifica: un error se corrige publicando una versión nueva.
- `release.json` contiene `feed_version`, `snapshot_id`, `code_version`, `corrections_version`, SHA-256 del ZIP, fechas de vigencia del feed y el resumen del validador GTFS.
- La versión se registra en `transit.feed_version` con el mismo SHA-256.

## 5. Detección de cambios en las fuentes

| Señal                                 | Dónde                                  | Acción                                                    |
| ------------------------------------- | -------------------------------------- | --------------------------------------------------------- |
| SHA-256 distinto al snapshot anterior | `.provenance.json`                      | Revisar el cambio antes de usar el snapshot como vigente  |
| Fecha `modified` de ArcGIS posterior  | `.provenance.json`, bloque `arcgis`     | Confirma un cambio del publicador                          |
| Ítem nuevo con otro año o nombre      | Descubrimiento de ArcGIS (ADR-0006)    | Registrar una fuente nueva y retirar la anterior           |
| Conteo de registros distinto          | `record_count`                          | Registrar la diferencia en `provenance.data_issue` si no se explica |

## 6. Base de datos

- Al cargar un snapshot, `provenance.data_source` guarda su `sha256` y `fetched_at`, y el identificador en `metadata.snapshot_id`.
- `loaded_by_run` guarda el `run_id` de la carga (ADR-0029, D14).
- Las filas de `provenance.source_record` son únicas por fuente, identificador externo y checksum, de modo que un registro sin cambios no se duplica entre snapshots.

## 7. Conservación y respaldo

| Capa                 | Conservación     | Respaldo (RGT-108) |
| -------------------- | ---------------- | ------------------ |
| Snapshots crudos     | Indefinida       | Sí                 |
| Capas derivadas      | Hasta regenerar  | No                 |
| Versiones publicadas | Indefinida       | Sí                 |

Ningún dato de `data/` se versiona en Git: los crudos pueden tener restricciones de licencia (ADR-0004) y el resto se regenera o se distribuye como artefacto.

## 8. Transición

Los archivos actuales de `data/raw/` (descarga del 2026-08-22) usan rutas fijas. RGT-33 los moverá a un snapshot con el identificador de esa descarga, ajustará el recolector para crear snapshots y escribirá `LATEST`.
