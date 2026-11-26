# Revisión del esquema canónico

| Campo   | Valor                                                                  |
| ------- | ---------------------------------------------------------------------- |
| Versión | 1.0                                                                    |
| Fecha   | 2026-11-25                                                             |
| Ticket  | [RGT-28](https://pablo2003cesar.atlassian.net/browse/RGT-28)           |
| Objeto  | [`database/schema/canonical.sql`](../../database/schema/canonical.sql) |
| ADR     | [ADR-0029](adr/0029-convenciones-del-esquema-canonico.md)              |

Revisión del esquema canónico antes de convertirlo en la migración inicial (RGT-29): claves, índices, restricciones, sistema de referencia, auditoría y compatibilidad con GTFS. Incorpora lo aprendido en el [spike de la ruta 801](../../prototype/routing/README.md). Las decisiones se implementan en la migración inicial salvo que se indique otro ticket.

## 1. Método

- **Análisis sintáctico** con `pglast` 8.9 (el analizador de PostgreSQL): el archivo es válido; 42 sentencias, 23 tablas, 3 tipos enumerados y 52 claves foráneas.
- **Análisis estructural automatizado** de claves foráneas sin índice y columnas de auditoría.
- **Revisión manual** contra la [referencia de GTFS Schedule](https://gtfs.org/documentation/schedule/reference/), los ADR vigentes y los hallazgos del spike.
- La instalación contra PostGIS 17-3.5 se verificará en CI al crear la migración (RGT-29).

## 2. Resumen

| Área                               | Estado                | Hallazgos | Severidad máxima |
| ---------------------------------- | --------------------- | --------- | ---------------- |
| Claves primarias e identificadores | Aceptable con ajustes | 3         | Media            |
| Índices                            | Incompleto            | 2         | Alta             |
| Restricciones e integridad         | Incompleto            | 7         | Media            |
| Sistema de referencia (SRID)       | Correcto              | 1         | Baja             |
| Auditoría                          | Ausente               | 2         | Alta             |
| Compatibilidad con GTFS            | Incompleta            | 6         | Alta             |
| Calidad y procedencia (spike)      | Incompleta            | 2         | Media            |
| Organización                       | Mejorable             | 2         | Media            |

## 3. Hallazgos y decisiones

### 3.1 Claves primarias e identificadores

| #   | Hallazgo                                                                                                                                                                    | Severidad | Decisión                                                                                                                                                                                                                                                                                |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H1  | Las entidades de transporte usan claves `text` (`route_id`, `stop_id`, `pattern_id`, …) sin formato definido; hoy podrían recibir identificadores de la fuente o inventados | Media     | **D1.** Las claves `text` se mantienen (compatibles con GTFS), pero con formato estable `<agencia>:<tipo>:<código>` (p. ej. `tubus:stop:801-094`) y una restricción `CHECK` de formato. El identificador de la fuente vive en `source_record.external_id`. Política detallada en RGT-52 |
| H2  | `pattern_stop` declara `PRIMARY KEY (pattern_id, stop_sequence)` y además `UNIQUE (pattern_id, stop_id, stop_sequence)`, que es redundante                                  | Baja      | **D2.** Eliminar la restricción `UNIQUE` redundante. Una misma parada puede repetirse en un patrón (circuitos), por lo que no se agrega unicidad por parada                                                                                                                             |
| H3  | Las tablas de observación (`vehicle_position`, `stop_event`, `eta_prediction`, `traffic_observation`) usan `bigint` identidad, adecuado                                     | —         | **D3.** Sin cambios; se evaluará particionamiento por tiempo cuando exista ingesta en tiempo real (épica RGT-9)                                                                                                                                                                         |

### 3.2 Índices

| #   | Hallazgo                                                                                                                                           | Severidad | Decisión                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H4  | **44 de 52 claves foráneas no tienen índice.** PostgreSQL no los crea automáticamente; afecta JOIN, borrados en cascada y validación de integridad | Alta      | **D4.** Crear un índice por cada clave foránea que no sea prefijo de la clave primaria o de otro índice. Una prueba de la migración verificará que no queden claves foráneas sin índice |
| H5  | Existen índices GiST en todas las geometrías, correcto                                                                                             | —         | Sin cambios                                                                                                                                                                             |

### 3.3 Restricciones e integridad

| #   | Hallazgo                                                                                                                                 | Severidad | Decisión                                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H6  | `route.route_color` y `route_text_color` son `char(6)` sin validar                                                                       | Baja      | **D5.** `CHECK (route_color ~ '^[0-9A-Fa-f]{6}$')`                                                                                                                                     |
| H7  | `route.mode` es texto libre (`'bus'`) en lugar del tipo de ruta de GTFS                                                                  | Media     | **D6.** Reemplazar por `route_type smallint` con los valores de GTFS (`CHECK`); el nombre comercial del sistema sigue en `system_name`                                                 |
| H8  | `stop_time` no exige `departure_seconds >= arrival_seconds`                                                                              | Media     | **D7.** Agregar la restricción y valores no negativos                                                                                                                                  |
| H9  | `service_calendar` permite un calendario sin ningún día activo                                                                           | Baja      | **D8.** `CHECK` que exija al menos un día                                                                                                                                              |
| H10 | Varias tablas con `valid_from`/`valid_to` no exigen que el fin sea posterior al inicio (`data_source`, `route`, `shape`, `fare_product`) | Media     | **D9.** `CHECK (valid_to IS NULL OR valid_to >= valid_from)` en todas                                                                                                                  |
| H11 | `transfer.transfer_type` no tiene `CHECK`; `fare_rule` no valida `max_distance_m >= min_distance_m`                                      | Baja      | **D10.** Agregar ambas restricciones (valores 0–5 de GTFS para `transfer_type`)                                                                                                        |
| H12 | Las claves foráneas no declaran comportamiento al borrar salvo en tablas hijas                                                           | Media     | **D11.** `ON DELETE RESTRICT` explícito para referencias a catálogo y procedencia; `CASCADE` solo en tablas de detalle (`pattern_stop`, `stop_time`, `frequency`, `service_exception`) |

### 3.4 Sistema de referencia espacial

| #   | Hallazgo                                                                                                                  | Severidad | Decisión                                                                                                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H13 | Todas las geometrías usan EPSG:4326, coherente con GeoJSON y GTFS; los cálculos de distancia en grados serían incorrectos | Baja      | **D12.** Almacenar en EPSG:4326. Las distancias y áreas se calculan con `geography` o transformando a **EPSG:32615 (UTM zona 15N)**, que cubre Guatemala. Se documenta en el ADR y en funciones auxiliares de la base |

### 3.5 Auditoría

| #   | Hallazgo                                                                                                               | Severidad | Decisión                                                                                                                                                                                                                                                                                    |
| --- | ---------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H14 | **Ninguna tabla tiene `created_at`** y solo 4 de 23 tienen `updated_at`, que además nunca se actualiza automáticamente | Alta      | **D13.** Todas las tablas de catálogo y operación tienen `created_at` y `updated_at` (`timestamptz NOT NULL DEFAULT now()`), con un trigger común que actualiza `updated_at`. Las tablas de observación solo `created_at`                                                                   |
| H15 | No queda registro de quién o qué proceso modificó un dato                                                              | Media     | **D14.** Columna `loaded_by_run` (identificador de ejecución del pipeline, `run_id`, [ADR-0027](adr/0027-observabilidad-con-opentelemetry-y-logs-estructurados.md)) en las tablas que carga el pipeline. Un historial completo de cambios se evaluará con el panel de correcciones (RGT-94) |

### 3.6 Compatibilidad con GTFS Schedule

| #   | Hallazgo                                                                                                                                              | Severidad | Decisión                                                                                                                                                             |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H16 | `stop` no tiene `location_type` (parada, estación, entrada, nodo, área de abordaje), necesario para estaciones de Transmetro y para `parent_station`  | Alta      | **D15.** Agregar `location_type smallint` (0–4, `CHECK`) y exigir `location` según el tipo                                                                           |
| H17 | `shape.geom` es `MultiLineString`: no garantiza un orden continuo de puntos y GTFS exige una secuencia ordenada (`shape_pt_sequence`)                 | Alta      | **D16.** Cambiar a `LineString` (un trazado continuo por patrón). El spike confirmó que el trazado de la ruta 801 es una sola línea continua                         |
| H18 | No existe `feed_info` (editor, versión, vigencia del feed)                                                                                            | Media     | **D17.** Tabla `feed_version` con editor, versión, vigencia y checksum del feed exportado (RGT-55)                                                                   |
| H19 | No existe el equivalente a `attributions.txt`; las licencias exigen atribución ([ADR-0024](adr/0024-confianza-interna-y-estimaciones-como-rangos.md)) | Media     | **D18.** La atribución se exporta desde `data_source.attribution`; se agrega `attribution_url`                                                                       |
| H20 | Las tarifas usan un modelo propio (`fare_product`, `fare_rule`)                                                                                       | Media     | **D19.** Se mantiene como modelo interno y se define su correspondencia con GTFS Fares v2 al implementar el exportador (RGT-51). Sin cambios en la migración inicial |
| H21 | `trip` no tiene `direction_id` ni `shape_id` propios; vienen de `route_pattern`                                                                       | —         | **D20.** Correcto: se derivan del patrón al exportar. Coherente con [ADR-0008](adr/0008-unidad-de-ruteo-ruta-variante-sentido-calendario.md)                         |

### 3.7 Calidad y procedencia (lecciones del spike)

| #   | Hallazgo                                                                                                                                                                            | Severidad | Decisión                                                                                                                                                          |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H22 | La calidad (`observation_quality`) existe solo en `stop` y `shape`; el spike mostró que la calidad es **por atributo**: la secuencia puede ser oficial y la ubicación no verificada | Media     | **D21.** Agregar `sequence_quality` a `pattern_stop` y `location_quality` (renombrando `quality`) a `stop`; tiempos y frecuencias heredan la calidad de su fuente |
| H23 | No hay dónde registrar las discrepancias entre fuentes que el spike documentó (número de parada distinto, direcciones desplazadas)                                                  | Media     | **D22.** Tabla `data_issue` (entidad, identificador, tipo de discrepancia, fuentes, estado, evidencia) para los reportes de calidad (RGT-40)                      |

### 3.8 Organización

| #   | Hallazgo                                                                                  | Severidad | Decisión                                                                                                                                                                      |
| --- | ----------------------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H24 | Todo vive en el esquema `public`, mezclando procedencia, red de transporte y tiempo real  | Media     | **D23.** Separar en esquemas: `provenance` (fuentes y registros), `transit` (red y servicio), `realtime` (observaciones y predicciones) y `community` (reportes)              |
| H25 | Los tipos `ENUM` de PostgreSQL solo admiten agregar valores, no quitarlos ni renombrarlos | Baja      | **D24.** Mantener `ENUM` para conjuntos estables definidos por el proyecto (`observation_quality`, `record_status`); usar `smallint` con `CHECK` para valores que define GTFS |

## 4. Implementación

| Decisiones                          | Ticket                                                       |
| ----------------------------------- | ------------------------------------------------------------ |
| D2, D4–D13, D15, D16, D21, D23, D24 | RGT-29 — migración inicial                                   |
| D1                                  | RGT-52 — identificadores GTFS estables (y formato en RGT-29) |
| D14                                 | RGT-29 (columna) y RGT-42 (carga desde el pipeline)          |
| D17, D18                            | RGT-29 (tablas y columnas) y RGT-55 (publicación)            |
| D19                                 | RGT-51 — exportador GTFS                                     |
| D22                                 | RGT-29 (tabla) y RGT-40 (validaciones)                       |
| D3                                  | Épica RGT-9 — tiempo real                                    |

Estado: implementado en la migración inicial `r0001_initial_schema` (RGT-29, [ADR-0030](adr/0030-migraciones-con-alembic-en-sql-explicito.md)).

## 5. Verificación prevista

La migración inicial (RGT-29) incluirá pruebas de integración contra PostGIS (marcador `integration`) que comprueben:

- que la base se crea desde cero de forma reproducible;
- que no quedan claves foráneas sin índice (D4);
- que todas las tablas de catálogo tienen `created_at` y `updated_at` con su trigger (D13);
- que las restricciones rechazan datos inválidos (D5–D10, D15).
