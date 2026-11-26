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

## Resultados

Los reportes generados se guardan en `output/` y los hallazgos se consolidan al cerrar el spike en `docs/research/`.
