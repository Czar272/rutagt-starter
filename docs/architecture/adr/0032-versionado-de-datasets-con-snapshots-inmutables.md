# ADR-0032: Versionar los datasets con snapshots inmutables y versiones publicadas por fecha

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-26 |
| Decisores   | @Czar272   |
| Tickets     | RGT-32     |
| Reemplaza a | —          |

## Contexto

[ADR-0004](0004-capas-de-datos-inmutables-con-procedencia.md) establece que las capas de datos nunca sobrescriben a la anterior y que cada descarga lleva procedencia, pero deja pendiente cómo se nombran y conservan las versiones (RGT-32). Hoy el recolector escribe cada fuente en una ruta fija (`data/raw/muniguate/tubus_stops_2025.geojson`) y el manifiesto en `data/raw/run_manifest.json`, de modo que **cada ejecución reemplaza a la anterior**:

- El manifiesto vigente corresponde a una ejecución del 2026-08-24 de una sola fuente que falló (HTTP 403). Reemplazó al de la ejecución del 2026-08-22 que descargó las cuatro capas GIS, y ya no queda registro de qué ejecución produjo esos archivos.
- Una nueva descarga de una capa que cambió en el portal borraría la versión con la que se validó el spike de la ruta 801.

Para que un feed publicado sea auditable hay que poder responder: ¿de qué descarga exacta proviene?, ¿con qué versión del código se transformó?, ¿qué cambió respecto de la versión anterior?

## Decisión

Adoptamos tres tipos de versión, una por cada naturaleza de la capa. La política completa, con ejemplos, está en [`docs/data/versionado-datasets.md`](../../data/versionado-datasets.md).

| Capa                            | Naturaleza                         | Versión                                                       | Mutabilidad                                                     |
| ------------------------------- | ---------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------- |
| `raw`                           | Evidencia de lo que dijo la fuente | **Snapshot** `AAAAMMDDTHHMMSSZ` (inicio de la ejecución, UTC) | Inmutable: se escribe una vez y nunca se modifica ni se borra   |
| `staging`, `normalized`, `gtfs` | Derivadas y reproducibles          | Identificador del snapshot del que derivan                    | Regenerables: una reconstrucción reemplaza el directorio entero |
| `published`                     | Artefacto distribuido a terceros   | **Versión de feed** `AAAA.MM.DD.N`                            | Inmutable: una corrección es una versión nueva                  |

1. **Snapshots crudos.** Cada ejecución del recolector crea `data/raw/<snapshot_id>/` de forma exclusiva (falla si ya existe) y escribe allí los archivos, su procedencia y el `run_manifest.json`. El `run_id` de la ejecución ([ADR-0027](0027-observabilidad-con-opentelemetry-y-logs-estructurados.md)) se conserva en el manifiesto. Cada snapshot contiene copia completa de lo descargado, sin deduplicar.
2. **Snapshot vigente.** `data/raw/LATEST` contiene el identificador del último snapshot **completo** (sin fuentes fallidas). Se actualiza solo después de escribir el manifiesto. Un snapshot parcial se conserva como evidencia, pero no se marca como vigente. Se usa un archivo y no un enlace simbólico por compatibilidad con Windows.
3. **Capas derivadas.** Se escriben en `data/<capa>/<snapshot_id>/` y su procedencia declara las entradas (snapshot y SHA-256 de cada archivo), el commit del código y la versión de las correcciones manuales. Como pueden regenerarse, no se respaldan.
4. **Versiones publicadas.** Un feed publicado se identifica como `AAAA.MM.DD.N` (fecha de publicación en `America/Guatemala` y secuencia del día desde 1). El mismo valor se usa en `feed_info.feed_version`, en `transit.feed_version` y en `data/published/<feed_version>/`. Cada versión incluye un `release.json` con el snapshot de origen, el commit, el SHA-256 del feed y el resultado del validador GTFS.
5. **Versiones de la fuente.** Cuando un publicador reemplaza una capa por otra (por ejemplo, la de 2025 por la de 2026), se registra como fuente nueva (`..._2026`) y la anterior se retira de la configuración sin borrar sus snapshots. Los cambios dentro de una misma fuente se detectan comparando el SHA-256 con el snapshot anterior.
6. **Base de datos.** Al cargar un snapshot, el pipeline registra su identificador en `provenance.data_source.metadata.snapshot_id` y su ejecución en `loaded_by_run` ([ADR-0029](0029-convenciones-del-esquema-canonico.md), D14).
7. **Conservación.** Los snapshots crudos y las versiones publicadas se conservan indefinidamente y entran en la estrategia de respaldo (RGT-108). Las capas derivadas se pueden borrar en cualquier momento.

## Alternativas consideradas

| Alternativa                                         | Ventajas                             | Desventajas                                                                                             | Motivo de descarte                                                     |
| --------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Mantener rutas fijas y confiar en el checksum       | Sin cambios en el código             | El archivo anterior se pierde; el checksum solo prueba que algo cambió, no qué                          | Incumple [ADR-0004](0004-capas-de-datos-inmutables-con-procedencia.md) |
| DVC o Git LFS                                       | Historial y deduplicación integrados | Herramienta y almacenamiento remoto adicionales; los datos de terceros quedarían en un servicio externo | Desproporcionado para 1,3 MB de datos y un equipo de una persona       |
| Almacenamiento direccionado por contenido (SHA-256) | Deduplicación automática             | Directorios ilegibles para una persona; requiere índice para reconstruir un snapshot                    | Se reevaluará si los snapshots superan 1 GB                            |
| Versión semántica para los feeds                    | Expresa compatibilidad               | Un feed de datos no tiene API que rompa; obliga a decidir qué es un cambio «mayor»                      | La fecha es lo que importa a quien consume un feed                     |
| Identificar snapshots por `run_id` (UUID)           | Ya existe                            | No se puede ordenar ni leer; no dice cuándo se descargó                                                 | Se conserva dentro del manifiesto                                      |

## Consecuencias

### Positivas

- Cualquier feed publicado se rastrea hasta el snapshot, el commit y las correcciones que lo produjeron.
- Una descarga nueva nunca destruye evidencia, incluso si falla a medias.
- Los identificadores se ordenan cronológicamente por nombre y se leen sin herramientas.

### Negativas y riesgos

- El almacenamiento crece con cada ejecución, aunque la fuente no haya cambiado. Con el volumen actual (1,3 MB por snapshot) no es un problema; se revisará con el umbral de 1 GB.
- Dos ejecuciones iniciadas en el mismo segundo colisionan; la segunda falla y debe repetirse.
- El recolector y la documentación de uso deben cambiar (RGT-33), y los archivos actuales de `data/raw/` deben moverse a un snapshot.

## Verificación

- `rutagt-collect fetch` crea un directorio nuevo por ejecución y nunca escribe en uno existente; las pruebas lo comprueban (RGT-33).
- `data/raw/LATEST` apunta a un snapshot cuyo manifiesto no tiene fuentes fallidas.
- Cada versión publicada tiene `release.json` y su `feed_version` coincide con `feed_info.txt` y con `transit.feed_version` (Sprint 8).

## Referencias

- [`docs/data/versionado-datasets.md`](../../data/versionado-datasets.md).
- [ADR-0004](0004-capas-de-datos-inmutables-con-procedencia.md), [ADR-0027](0027-observabilidad-con-opentelemetry-y-logs-estructurados.md), [ADR-0029](0029-convenciones-del-esquema-canonico.md).
- [GTFS Schedule, `feed_info.txt`](https://gtfs.org/documentation/schedule/reference/#feed_infotxt).
