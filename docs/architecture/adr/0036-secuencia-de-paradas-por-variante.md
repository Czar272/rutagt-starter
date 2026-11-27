# ADR-0036: Determinar la secuencia de paradas con el rutero oficial y, sin él, por posición sobre el trazado

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-27 |
| Decisores   | @Czar272   |
| Tickets     | RGT-43     |
| Reemplaza a | —          |

## Contexto

Las capas municipales dicen qué variantes sirven a cada parada (`Codigoruta`), pero no en qué orden ni en qué sentido. El spike de la ruta 801 ([informe](../../research/spike-ruta-801.md)) mostró que:

- La secuencia por sentido solo se obtiene del **rutero oficial** (PDF). Hoy solo el de la ruta 801 (versión 4, 47 paradas) está transcrito y validado contra el documento (RGT-127).
- El número de «Parada NNN» no sirve para ordenar: en la 801 está corrido entre 094 y 104. Asignar por ese número daba la parada siguiente.
- Proyectar las paradas sobre el trazado y alinear el rutero en orden, por similitud de dirección, reprodujo la revisión manual 47 de 47.
- Ordenar solo por proximidad no basta: en un circuito, las paradas de ida y de regreso de la misma calle quedan intercaladas.

Las otras 19 variantes (Transmetro y TuBus) no tienen rutero transcrito todavía; se solicitarán a la Municipalidad (RGT-49).

## Decisión

El constructor canónico ([ADR-0035](0035-constructor-canonico-y-carga-idempotente.md)) produce `pattern_stop` para cada variante con trazado y paradas:

1. **Proyección**: cada parada de la variante (andenes, no estaciones) se ubica en metros a lo largo de su trazado, con distancias geodésicas iguales a las de `distance_m`.
2. **Con rutero** (`data/reference/ruteros/*.json`): cada parada del rutero se asigna a una parada distinta de la capa con una alineación monótona sobre el orden proyectado (programación dinámica). El puntaje combina similitud de texto (0,6) y coincidencia de números de vía (0,4). En un circuito se prueba cada punto de inicio y se elige el de mejor alineación.
3. **Sin rutero**: la secuencia es el orden sobre el trazado, con calidad `probable` y la incidencia `secuencia_sin_rutero` (warning) por variante.

### Confirmación y calidad (ADR-0031)

| Caso                                                        | `sequence_quality` | Incidencia                       |
| ----------------------------------------------------------- | ------------------ | -------------------------------- |
| Rutero con revisión manual y asignación igual a la revisión | `official`         | —                                |
| Rutero con revisión manual y asignación distinta            | `probable`         | `asignacion_contradice_revision` |
| Rutero sin revisión y dirección con puntaje ≥ 0,75          | `official`         | —                                |
| Rutero sin revisión y puntaje menor                         | `probable`         | `parada_por_revisar`             |
| Sin rutero                                                  | `probable`         | `secuencia_sin_rutero`           |

La revisión manual es parte del rutero transcrito: cada parada guarda el registro de la capa que eligió la revisión (`layer_external_id`) y los registros excluidos con su motivo. Si la Municipalidad renumera la capa, la asignación deja de coincidir y aparece como incidencia en vez de confirmarse sola.

### Otros resultados

- **Código oficial**: una parada asignada y confirmada recibe el código del rutero en `stop.stop_code` (la «Parada 100» de la capa es la 098 del rutero). Si dos ruteros le dan códigos distintos, no se asigna y queda `codigo_contradictorio`.
- **Paradas fuera del rutero**: las que la capa asigna a la variante pero el rutero no incluye quedan fuera de la secuencia, con `parada_fuera_de_rutero` y el motivo de la revisión (FID 91 y 92 de la 801).
- **Atributos de la variante** (`route_pattern.attributes`): `circuit` (el trazado termina donde empieza), `sequence_source` (el rutero o `trazado`) y `terminal_stop_id` (parada terminal del rutero).
- **`shape_dist_traveled_m`**: se guarda solo si las distancias crecen a lo largo de la secuencia, como exige GTFS.
- **Rutero como fuente**: cada rutero es una fila de `provenance.data_source` con el SHA-256 del PDF.
- **Robustez**: un rutero de una variante que no está en el dataset da `rutero_sin_variante`. Un rutero con más paradas que la capa da `rutero_incompleto` y se ordena por el trazado.

### Sentido

La secuencia cubre la variante completa, incluido el cierre del circuito. Separarla en sentidos (`direction_id`) en la parada terminal es parte del modelado de variantes y sentidos operativos (RGT-44), que usará `terminal_stop_id`.

## Alternativas consideradas

| Alternativa                               | Ventajas             | Desventajas                                       | Motivo de descarte                                    |
| ----------------------------------------- | -------------------- | ------------------------------------------------- | ----------------------------------------------------- |
| Ordenar por el número de «Parada NNN»     | Trivial              | Numeración corrida y repetida en la capa          | Asigna paradas equivocadas (spike de la 801)          |
| Ordenar por cercanía a la parada anterior | No requiere trazado  | Intercala ida y regreso en calles compartidas     | No respeta el recorrido real                          |
| Cargar secuencia solo con rutero          | Solo datos oficiales | 19 de 20 variantes quedan sin red para el ruteo   | Una secuencia `probable` marcada es más útil que nada |
| Asignar cada parada por su mejor puntaje  | Simple               | Varias paradas del rutero toman el mismo registro | La alineación monótona garantiza registros distintos  |

## Consecuencias

### Positivas

- La ruta 801 queda con secuencia `official` reproducible y verificada contra la revisión humana.
- Todas las variantes con trazado tienen una secuencia utilizable, con calidad e incidencia que dicen cuánto confiar en ella.
- Agregar el rutero de otra variante es agregar un archivo JSON: no requiere código.

### Negativas y riesgos

- El orden por trazado puede equivocarse si dos tramos del recorrido pasan muy cerca. Por eso queda `probable` y no se publica como oficial.
- Transcribir y revisar ruteros es trabajo manual; cada rutero debe validarse contra su PDF antes de agregarse.

## Verificación

- Pruebas unitarias de puntajes, alineación, proyección, circuitos, confirmación por revisión e incidencias.
- Con el fixture real (ruta 801 completa), la secuencia reproduce la revisión de RGT-127 47 de 47, con calidad `official`, códigos oficiales y terminal.
- Pruebas de integración: `pattern_stop` se carga, se recarga sin cambios y se recorta cuando una secuencia se acorta.

## Referencias

- [Informe del spike de la ruta 801](../../research/spike-ruta-801.md).
- [ADR-0008](0008-unidad-de-ruteo-ruta-variante-sentido-calendario.md), [ADR-0031](0031-escala-de-calidad-y-reglas-de-vigencia.md), [ADR-0035](0035-constructor-canonico-y-carga-idempotente.md).
- [GTFS Schedule Reference — stop_times.txt](https://gtfs.org/documentation/schedule/reference/#stop_timestxt).
