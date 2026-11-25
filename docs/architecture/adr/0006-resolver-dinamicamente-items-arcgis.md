# ADR-0006: Resolver dinámicamente los ítems ArcGIS vigentes

| Campo       | Valor          |
| ----------- | -------------- |
| Estado      | Aceptado       |
| Fecha       | 2026-08-15     |
| Decisores   | @Czar272       |
| Tickets     | RGT-18, RGT-22, RGT-23 |
| Reemplaza a | —              |

## Contexto

Las capas de Transmetro y TuBus se publican en el portal de datos abiertos DIGM de la Municipalidad de Guatemala sobre ArcGIS Online. Durante la verificación se comprobó que los identificadores de ítem del inventario municipal de 2025 dejaron de ser los vigentes: cada nueva publicación puede crear un ítem distinto. Un recolector con identificadores fijos descargaría datos desactualizados o fallaría.

## Decisión

El recolector **descubre el ítem vigente mediante una búsqueda en el catálogo de ArcGIS** (`discover_query`, por propietario y título), filtrando servicios públicos de tipo _Feature Service_ y ordenando por fecha de modificación descendente.

Si la búsqueda no devuelve resultados, usa un **identificador de respaldo** (`fallback_item_id`) declarado en `config/sources.json`. El ítem efectivamente usado se registra en la procedencia (`resolved_item_id`, `resolved_service_url`, `resolved_layer_url`).

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Identificadores fijos | Determinista | Se rompe o queda obsoleto con cada republicación | Comprobado como frágil |
| Descarga manual desde el portal | Sin código | No reproducible ni automatizable | Contrario a [ADR-0004](0004-capas-de-datos-inmutables-con-procedencia.md) |

## Consecuencias

### Positivas

- El recolector obtiene la versión más reciente sin cambios de código.
- La procedencia registra exactamente qué ítem se descargó.

### Negativas y riesgos

- Un ítem nuevo con título similar pero contenido distinto podría seleccionarse por error; se mitiga validando geometrías y campos requeridos y comparando conteos entre ejecuciones.

## Verificación

- `discover_arcgis_item` en `pipeline/collectors/collect.py`.
- Cada fuente `arcgis_feature_service` de `config/sources.json` declara `discover_query` y `fallback_item_id`.

## Referencias

- `docs/data/plan-producto-y-datos.md`, sección 3 «Hallazgos de calidad».
