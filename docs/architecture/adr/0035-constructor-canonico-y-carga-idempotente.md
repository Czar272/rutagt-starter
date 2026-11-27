# ADR-0035: Construir la red canónica con identificadores estables y cargarla de forma idempotente

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-27 |
| Decisores   | @Czar272   |
| Tickets     | RGT-42     |
| Reemplaza a | —          |

## Contexto

El [ADR-0033](0033-contrato-de-normalizadores.md) dejó definidos el adaptador y la capa staging, y reservó para un constructor canónico y un cargador las decisiones que combinan registros: estaciones, identificadores y calidad. Con los cuatro lotes municipales de 2025 en staging se observó:

- La capa de Transmetro publica un registro por estación **y variante**. Los 169 registros son 109 andenes físicos: las variantes de una línea repiten el andén con coordenadas idénticas (Bolívar aparece 6 veces en 2 andenes).
- Una misma estación aparece con nombres que solo difieren en el prefijo o en tildes («Estación Atlántida» y «Atlántida», «Estacion Santa Teresa»).
- Las variantes 12000/12001/12002 y 18001/18002 comparten trazado (`trazado_compartido`).
- El `FID` de la capa no es un identificador estable: la Municipalidad puede renumerarlo al republicar.
- TuBus tiene posibles duplicados (`numero_repetido`, FID 143/258 a 6 m) y Transmetro un sentido repetido (Granai, FID 144/145), que no se pueden resolver sin verificación.
- El esquema solo permite un `source_record_id` por entidad, pero un andén o un trazado compartido provienen de varios registros.
- `provenance.data_issue` no tiene clave natural: una segunda carga duplicaría las incidencias.

## Decisión

### Flujo

```text
staging/<snapshot>/<source_id>.json ──rutagt-canonical──► normalized/<snapshot>/canonical.json ──rutagt-load──► PostGIS
```

`rutagt-canonical` es una función pura sobre los lotes (más la procedencia cruda y `config/agencies.json`) y escribe un `CanonicalDataset` determinista con su `.provenance.json`. `rutagt-load` lo carga en una sola transacción. Un lote con problemas `error` no pasa a la capa canónica.

### Identificadores (`<agencia>:<tipo>:<código>`)

| Entidad       | Código                                                  | Ejemplo                                            |
| ------------- | ------------------------------------------------------- | -------------------------------------------------- |
| Ruta          | Código de la ruta o línea                               | `transmetro:route:12`, `tubus:route:801`           |
| Variante      | Código de la variante; sin variantes, el de la ruta     | `transmetro:pattern:12001`, `tubus:pattern:801`    |
| Trazado       | Código menor de las variantes con coordenadas idénticas | `transmetro:shape:12000` (12000, 12001 y 12002)    |
| Estación      | Nombre normalizado sin el prefijo «Estación»            | `transmetro:stop:bolivar`                          |
| Andén         | Estación + número por orden del primer registro         | `transmetro:stop:bolivar.1`                        |
| Parada simple | Nombre normalizado; si se repite, con número por orden  | `tubus:stop:parada-067`, `tubus:stop:parada-190.2` |

Los códigos salen del dato publicado, no del `FID`. La agencia de cada fuente se declara en `config/sources.json` (`agency`) y sus datos en `config/agencies.json`.

### Paradas, andenes y estaciones

- Los registros con el mismo nombre normalizado a menos de **1 m** son una sola parada física, con todos sus registros como procedencia.
- Las fuentes con `group_stations` (Transmetro) agrupan sus paradas por nombre normalizado en una estación (`location_type = 1`) ubicada en el centroide de sus andenes, que quedan como hijos (`parent_station_id`, `platform_code`).
- No se fusionan paradas distintas por cercanía ni se resuelven duplicados posibles: quedan como incidencias abiertas para curación.
- Incidencias nuevas del constructor: `estacion_dispersa` (warning, andén a más de 300 m del centro; el mayor de 2025, Reformita, está a 101 m), `nombres_unificados` (info) y `sentido_contradictorio` (warning).

### Calidad (ADR-0031)

| Dato                       | Nivel      | Motivo                                        |
| -------------------------- | ---------- | --------------------------------------------- |
| Ubicación de andén/parada  | `official` | Dato publicado sin transformación sustantiva  |
| Ubicación de una estación  | `probable` | Centroide calculado con un método documentado |
| Trazado de un solo tramo   | `official` | Geometría publicada                           |
| Trazado unido desde tramos | `probable` | Orden reconstruido por `chain_segments`       |

### Procedencia

- `provenance.source_record` guarda cada registro con el SHA-256 de su JSON canónico; un registro sin cambios no se repite entre cargas.
- La tabla nueva `provenance.entity_source_record` (append-only) enlaza cada entidad con **todos** sus registros de origen; `source_record_id` de la entidad apunta al primero.
- `provenance.data_source` toma la vigencia del snapshot cargado: `fetched_at`, `sha256` y la capa resuelta.

### Carga idempotente

- Entidades: `INSERT … ON CONFLICT DO UPDATE … WHERE` algún valor es distinto. Una fila sin cambios conserva `updated_at` y `loaded_by_run`, así que recargar el mismo dataset no modifica ninguna fila.
- `location_assessed_at` y `quality_assessed_at` solo cambian si cambian la geometría o la calidad.
- Las rutas, variantes y paradas de una fuente cargada que ya no aparecen pasan a `status = 'retired'`; nunca se borran. Si reaparecen, vuelven a `active`.
- Las incidencias del pipeline tienen `issue_key` (SHA-256 de fuente, tipo, entidad y evidencia), único por fuente. Una incidencia existente conserva el estado que le dio la curación (`confirmed`, `dismissed`); una abierta que deja de detectarse pasa a `resolved` y se reabre si reaparece.

## Alternativas consideradas

| Alternativa                               | Ventajas                   | Desventajas                                                     | Motivo de descarte                                     |
| ----------------------------------------- | -------------------------- | --------------------------------------------------------------- | ------------------------------------------------------ |
| Identificadores a partir del `FID`        | Triviales y únicos         | Cambian si la Municipalidad renumera la capa                    | Romperían referencias de feeds y reportes entre cargas |
| Un andén por registro de la fuente        | Sin agrupar                | Repite el mismo andén por variante; GTFS con paradas duplicadas | Contradice la realidad física observada                |
| Fusionar paradas cercanas (p. ej. a 15 m) | Resuelve duplicados obvios | Une paradas de sentidos opuestos en la misma calle              | Una fusión sin evidencia es una corrección arbitraria  |
| Borrar y reinsertar en cada carga         | Simple                     | Pierde `created_at`, estados de curación y referencias externas | Viola la trazabilidad                                  |
| Cargar directamente desde staging         | Un paso menos              | Mezcla decisiones de combinación con escritura en la base       | Sin un artefacto revisable entre staging y la base     |

## Consecuencias

### Positivas

- Recargar el mismo snapshot no cambia nada y una carga fallida no deja cambios a medias.
- Cada entidad conserva todos sus registros originales, también los repetidos por variante.
- La red canónica es un archivo revisable y versionado por snapshot antes de tocar la base.

### Negativas y riesgos

- El número de un andén o de una parada repetida depende del orden de los registros: si la fuente agrega un andén nuevo antes que otro, la numeración puede cambiar.
- Agrupar por nombre exige que la fuente nombre igual a la misma estación: un andén con el nombre mal escrito formaría una estación aparte. Se corrige en el adaptador con evidencia.
- La relación entre paradas y variantes sin secuencia (`pattern_ids`) queda en el dataset canónico, no en la base, hasta la reconciliación de secuencias (RGT-43).

## Verificación

- Pruebas unitarias del constructor con lotes sintéticos y con el fixture real de los normalizers: agrupación, identificadores, calidad, incidencias y determinismo.
- Pruebas de integración de la carga: segunda carga sin cambios (`updated_at` y conteos iguales), actualización, retiro y reactivación, resolución y reapertura de incidencias, estado de curación conservado y transacción revertida ante un error.
- Las pruebas de migraciones verifican que `entity_source_record` cumple las convenciones del ADR-0029.

## Referencias

- [ADR-0029](0029-convenciones-del-esquema-canonico.md), [ADR-0031](0031-escala-de-calidad-y-reglas-de-vigencia.md), [ADR-0033](0033-contrato-de-normalizadores.md).
- [Perfil de los datasets](../../data/perfil-datasets.md).
- [GTFS Schedule Reference — stops.txt](https://gtfs.org/documentation/schedule/reference/#stopstxt).
- [PostgreSQL — INSERT … ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT).
