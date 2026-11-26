# Spike de ruteo: ruta 801 de TuBus

Investigación técnica aislada ([ADR-0013](../../docs/architecture/adr/0013-aislar-spikes-del-codigo-productivo.md)) para determinar hasta dónde se puede construir un itinerario con los datos abiertos disponibles y qué información adicional hay que solicitar a las instituciones.

| Campo  | Valor                                                                                        |
| ------ | -------------------------------------------------------------------------------------------- |
| Ticket | [RGT-115](https://pablo2003cesar.atlassian.net/browse/RGT-115) y subtareas RGT-126 a RGT-133 |
| Sprint | 4 — Spike ruta 801                                                                           |
| Estado | En curso                                                                                     |

> Este código es experimental. No se importa desde `src/rutagt/` y no forma parte del producto. Lo que se decida conservar se reimplementará en el paquete mediante tickets ordinarios.

## Por qué la ruta 801

La capa municipal de paradas de TuBus asocia cada parada a un código de ruta (`Codigoruta`), pero no indica su orden ni su sentido. El rutero oficial de la ruta 801 (versión 4, vigente desde marzo de 2025) sí enumera las paradas en orden, con dirección y zona, por lo que permite reconstruir la secuencia y medir la calidad de la capa abierta.

## Datos

| Archivo                                                              | Origen                                                                                                                                               |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data/route_801_official.json`                                       | Transcripción manual del rutero oficial (PDF de la Municipalidad de Guatemala): 47 paradas numeradas del #063 al #109, horarios de servicio y fuente |
| `data/raw/muniguate/tubus_stops_2025.geojson` (raíz del repositorio) | Capa oficial de paradas de TuBus descargada con `uv run rutagt-collect fetch --source muniguate_tubus_stops_2025`                                    |

## Ejecución

Desde la raíz del repositorio, con los datos crudos ya descargados:

```powershell
uv run python prototype/routing/analyze_route.py
```

El script compara cada parada del rutero con los registros GeoJSON de la ruta 801 y las clasifica:

| Clase           | Criterio                                                                  |
| --------------- | ------------------------------------------------------------------------- |
| `EXACT`         | El número de parada coincide y la dirección es muy similar (≥ 0,75)       |
| `LIKELY`        | El número coincide y el puntaje total es ≥ 0,70                           |
| `ADDRESS_MATCH` | El número no coincide, pero la zona sí y la dirección es similar (≥ 0,70) |
| `AMBIGUOUS`     | Puntaje total ≥ 0,40 sin cumplir lo anterior                              |
| `UNMATCHED`     | Sin candidato aceptable                                                   |

Puntaje: 0,55 por número de parada, 0,10 por zona y 0,35 × similitud de dirección normalizada.

### Auditoría de candidatos (RGT-126)

```powershell
uv run python prototype/routing/audit_candidates.py
```

Genera `output/route_801_candidate_audit.md` y `.json` con las paradas que no son `EXACT` o que tienen alertas, sus tres mejores candidatos y alertas por:

- salto mayor a 800 m respecto de la parada anterior de la secuencia;
- número de parada del registro distinto al del rutero o repetido en varios registros;
- registros fuera de orden respecto de la secuencia;
- registros sin asignar con una dirección más parecida que la del candidato elegido.

### Correspondencia revisada (RGT-127)

```powershell
uv run python prototype/routing/review_mapping.py
```

Proyecta los registros GeoJSON sobre el trazado oficial de la ruta (`linear_reference.py`), los ordena por su posición en el recorrido y alinea con ellos la secuencia del rutero conservando el orden. Las decisiones que requirieron criterio (asignaciones manuales, notas y registros excluidos) están declaradas en el script. Genera:

- `data/route_801_reviewed_mapping.json`: correspondencia parada → FID con su evidencia; es la referencia para validar el reconciliador (RGT-128).
- `output/route_801_reviewed_mapping.md`: reporte legible.

La transcripción `data/route_801_official.json` se validó contra la tabla del PDF oficial (47 de 47 paradas coinciden); el método y el checksum del documento están en su campo `source`.

### Reconciliación ordenada (RGT-128)

```powershell
uv run python prototype/routing/sequence_reconciler.py
uv run pytest prototype/routing
```

Reemplaza la asignación parada por parada de `analyze_route.py`, que priorizaba el número en el nombre del registro y fallaba con la numeración corrida de la capa municipal. El reconciliador:

1. ordena los registros por su posición a lo largo del trazado oficial;
2. compara direcciones combinando similitud de texto (60 %) y coincidencia de números de calle y avenida (40 %);
3. asigna cada parada a un registro distinto conservando el orden (alineación monótona); el número en el nombre del registro solo se usa como alerta.

Genera `output/route_801_sequence_reconciliation.md` y termina con código 1 si el resultado difiere de la correspondencia revisada (`data/route_801_reviewed_mapping.json`). Resultado actual: 47 de 47 paradas iguales a la revisión, 0 registros reutilizados y FID 91 y FID 92 sin parada.

### GeoJSON enriquecido (RGT-129)

```powershell
uv run python prototype/routing/enrich_route.py
```

Genera `output/route_801_enriched.geojson` (y su `.provenance.json`) con:

| `feature_type`  | Contenido                                                                                                                                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `shape`         | Trazado oficial de la ruta y su longitud                                                                                                                                                                               |
| `stop`          | Las 47 paradas en orden oficial: código, dirección del rutero, ubicación de la capa, FID asignado, posición y distancia a la siguiente parada, puntaje y estado de la asignación, discrepancias y calidad por atributo |
| `excluded_stop` | Registros de la capa sin parada en el rutero vigente                                                                                                                                                                   |

La calidad usa los niveles de `observation_quality` del esquema canónico: secuencia, código y dirección son `official` (rutero); la ubicación es `probable` cuando la capa y el rutero concuerdan y `unverified` cuando discrepan. Los metadatos incluyen la procedencia de cada fuente con su checksum.

## Resultados

Los reportes generados se guardan en `output/` y los hallazgos se consolidan al cerrar el spike en `docs/research/`.
