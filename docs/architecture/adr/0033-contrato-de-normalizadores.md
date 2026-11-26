# ADR-0033: Normalizar en dos pasos con adaptadores por fuente y modelos de staging validados

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-26 |
| Decisores   | @Czar272   |
| Tickets     | RGT-35     |
| Reemplaza a | —          |

## Contexto

El Sprint 6 traduce las capas crudas de Transmetro y TuBus al esquema canónico (ADR-0029). El [perfil de los datasets](../../data/perfil-datasets.md) mostró que cada fuente necesita reglas propias:

- códigos de ruta como texto o como número;
- sentido escrito dentro del nombre de la estación;
- variantes sin trazado propio;
- zonas que contradicen la dirección.

Otras decisiones solo tienen sentido al combinar fuentes: unir las estaciones repetidas por línea, asignar identificadores canónicos y detectar transbordos.

Sin un contrato común, cada normalizador resolvería a su manera la lectura del snapshot, el registro, la procedencia y el manejo de errores. Sería difícil probarlos y auditarlos.

## Decisión

### Flujo en tres pasos

```text
raw/<snapshot>/  ──adaptador por fuente──►  staging/<snapshot>/<source_id>.json
                 ──constructor canónico──►  normalized/<snapshot>/
                 ──cargador (RGT-42)─────►  PostGIS
```

| Paso                                           | Responsabilidad                                                                                                                                                     | No hace                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **Adaptador** (uno por `source_id`)            | Traduce cada registro crudo a un modelo de staging con el vocabulario canónico: tipos, limpieza de texto, geometría, códigos. Reporta problemas como `Issue`        | Asignar identificadores canónicos, combinar fuentes, leer archivos |
| **Constructor canónico** (por tipo de entidad) | Combina lotes de staging: estaciones y andenes, rutas y variantes, identificadores `<agencia>:<tipo>:<código>`, nivel de calidad (ADR-0031), transbordos candidatos | Leer el formato de una fuente concreta                             |
| **Cargador**                                   | Escribe en PostGIS de forma idempotente, con `source_record` y `data_issue`                                                                                         | Transformar datos                                                  |

Este ADR fija el contrato del adaptador y del staging. El constructor canónico y el cargador se implementan en RGT-36 a RGT-42 sobre este contrato.

### Contrato del adaptador

- **Firma:** es una función pura `(RawInput) -> StagingBatch`, registrada con `@register_adapter("<source_id>")`. Se registra por fuente y no por tipo, porque las reglas dependen del dataset, no del protocolo de descarga.
- **Entrada:** `RawInput` lleva `source_id`, `snapshot_id`, el contenido ya leído y su procedencia. El adaptador no accede a disco, red ni base de datos.
- **Salida:** `StagingBatch` contiene registros `StagedStop`, `StagedRoute` y `StagedShape`, además de `Issue`.
  - Los modelos son **Pydantic estrictos e inmutables**: no admiten campos desconocidos ni conversiones implícitas de tipo.
  - Cada registro lleva `SourceRef`, con fuente, identificador externo y atributos crudos, para cargarlo en `provenance.source_record`.
- **Problemas:** un registro con problemas no lanza una excepción; se reporta un `Issue` con severidad y código.
  - `error`: el lote no pasa a la capa canónica y el comando termina con código 1.
  - `warning` e `info`: se registran y se cargan en `provenance.data_issue`.
  - RGT-40 define las validaciones geoespaciales y su severidad.
- **Correcciones manuales:** se versionan en el repositorio junto al adaptador que las aplica, así que `corrections_version` es el mismo commit que `code_version`.

### Responsabilidades del runner (`rutagt-normalize`)

- **Selección:** lee el snapshot vigente o el indicado, y ejecuta las fuentes con adaptador o las pedidas con `--source`.
- **Integridad:** verifica que el SHA-256 del archivo crudo coincida con su procedencia antes de usarlo.
- **Contexto de registro:** el log lleva `run_id`, `snapshot_id` y `source_id` (ADR-0027).
- **Salida:** escribe cada lote y su procedencia de forma atómica en `data/staging/<snapshot_id>/`. La procedencia incluye entradas, commit, conteos por entidad y problemas por severidad (ADR-0032). También escribe un `run_manifest.json`.
- **Fallos:** una fuente que falla (archivo ausente o alterado, JSON inválido, modelo inválido o error inesperado) no detiene las demás.
- **Códigos de salida:** 0 éxito, 1 fallas o problemas `error`, 2 configuración.

## Alternativas consideradas

| Alternativa                                               | Ventajas                | Desventajas                                                                                                             | Motivo de descarte                                      |
| --------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Un paso directo de crudo a la base                        | Menos código            | Sin capa intermedia inspeccionable; mezcla reglas de fuente con reglas de combinación; pruebas lentas con base de datos | Dificulta auditar qué hizo cada fuente                  |
| Adaptadores por tipo de fuente (`arcgis_feature_service`) | Menos registros         | Dos capas ArcGIS de la Municipalidad tienen campos y reglas distintas                                                   | Las reglas son por dataset                              |
| `dataclasses` o diccionarios                              | Sin dependencias        | Sin validación declarativa; los diccionarios ya mostraron sus límites (pipeline-design §8)                              | Pydantic se usará también en la API (ADR-0022)          |
| pandas o GeoPandas                                        | Operaciones vectoriales | Dependencias pesadas para unos cientos de registros; tipos menos estrictos                                              | Desproporcionado para el volumen actual                 |
| Lanzar excepción ante un registro inválido                | Simple                  | Un registro malo detiene toda la fuente y oculta los demás problemas                                                    | Los problemas son datos de primera clase (`data_issue`) |

## Consecuencias

### Positivas

- Cada adaptador se prueba con datos en memoria, sin disco ni base de datos.
- La capa staging permite revisar, para cada fuente, qué se interpretó y qué problemas se encontraron, antes de tocar la base.
- La procedencia y el manejo de errores son iguales para todas las fuentes.

### Negativas y riesgos

- Una dependencia nueva: `pydantic`.
- Los modelos de staging pueden necesitar campos nuevos en RGT-36 a RGT-39. Mientras no se cargue la base, cambiarlos no rompe datos persistidos.
- Dos lugares para la lógica (adaptador y constructor) exigen respetar la frontera: nada de reglas de combinación en los adaptadores.

## Verificación

- `src/rutagt/pipeline/normalizers/`: `models.py`, `base.py`, `runner.py` y `cli.py`, con pruebas en `tests/pipeline/normalizers/`.
- `uv run rutagt-normalize` escribe `data/staging/<snapshot>/<source_id>.json` con su `.provenance.json`.
- Un adaptador nuevo se agrega con un módulo registrado e importado en `normalizers/__init__.py`, igual que los collectors.

## Referencias

- [ADR-0026](0026-paquete-rutagt-y-patrones-del-pipeline.md), [ADR-0029](0029-convenciones-del-esquema-canonico.md), [ADR-0031](0031-escala-de-calidad-y-reglas-de-vigencia.md), [ADR-0032](0032-versionado-de-datasets-con-snapshots-inmutables.md).
- [Perfil de los datasets municipales](../../data/perfil-datasets.md).
- [Diseño del pipeline](../pipeline-design.md).
