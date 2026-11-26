# Inventario maestro de cobertura de datos

| Campo        | Valor                                                        |
| ------------ | ------------------------------------------------------------ |
| Versión      | 1.0                                                          |
| Fecha        | 2026-11-26                                                   |
| Ticket       | [RGT-30](https://pablo2003cesar.atlassian.net/browse/RGT-30) |
| Datos crudos | Capas descargadas el 18 y 22 de agosto de 2026               |

Matriz de qué datos existen para cada sistema de transporte del Área Metropolitana, de qué fuente provienen y qué falta. Sirve para priorizar la adquisición de datos y para saber qué puede prometer el producto en cada sistema. Las cifras provienen de las capas en `data/raw/` y del [spike de la ruta 801](../research/spike-ruta-801.md).

## 1. Leyenda

| Símbolo | Significado                                                                      |
| ------- | -------------------------------------------------------------------------------- |
| ✔       | Disponible en una fuente oficial **estructurada** y automatizable                |
| ◐       | Parcial: solo documental (PDF, HTML), incompleta o por variante                  |
| ✖       | No disponible en fuentes abiertas conocidas                                      |
| ?       | Fuente identificada, contenido sin verificar                                     |

La columna **Confianza** usa la escala de calidad de [ADR-0031](../architecture/adr/0031-escala-de-calidad-y-reglas-de-vigencia.md), de mayor a menor: `official` > `verified` > `probable` > `estimated` > `community` > `unverified`.

## 2. Matriz por sistema

| Sistema | Rutas | Paradas | Geometría | Secuencia y sentido | Horario | Frecuencia | Tarifa | Licencia | Confianza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Transmetro** | ✔ | ✔ | ✔ | ? | ? | ✖ | ? | ◐ | `official` en geometría y paradas; sin secuencia |
| **TuBus** | ✔ | ✔ | ✔ | ◐ | ◐ | ✖ | ✖ | ◐ | `official` en geometría; secuencia `official` solo en la ruta 801 |
| **Transurbano** (SIGA) | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ | ✖ | Sin datos |
| **Rutas urbanas concesionadas** (modelo 2026) | ◐ | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ | ? | `unverified` |
| **TransMIO** (Villa Nueva) | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | Sin datos |
| **Transporte de Mixco** (Express Mixco y rutas locales) | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | Sin datos |
| **Transpinula** (Santa Catarina Pinula) | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | Sin datos |
| **Extraurbanos** (DGT) | ? | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ | ? | `unverified` |

## 3. Detalle por sistema

### Transmetro

| Dato | Estado | Fuente | Observaciones |
| --- | --- | --- | --- |
| Rutas | ✔ | `muniguate_transmetro_routes_2025` (ArcGIS) | 12 trazados: 7 líneas (1, 2, 6, 7, 12, 13, 18) y 5 variantes (extensión, directos y expresos) identificadas por `Codigoruta` |
| Paradas | ✔ | `muniguate_transmetro_stops_2025` (ArcGIS) | 169 registros con 109 nombres únicos: una estación se repite por cada línea que la sirve. Se modelan como estaciones (`location_type = 1`) con andenes por línea |
| Geometría | ✔ | Capa de rutas | 11 `LineString`; la Línea 18 es un `MultiLineString` de 4 tramos contiguos (separación 0 m) que se fusiona en un solo trazado al normalizar |
| Secuencia y sentido | ? | `muniguate_transmetro_catalog` (HTML) | La capa no tiene orden ni sentido; verificar si el catálogo oficial lista las estaciones en orden |
| Horario | ? | `muniguate_transmetro_catalog` (HTML) | Por verificar; no se esperan horarios por franja en fuentes abiertas |
| Frecuencia | ✖ | — | Requiere datos de operación |
| Tarifa | ? | Información pública | Por verificar; no hay fuente estructurada |
| Licencia | ◐ | Metadatos del portal | Uso público y reutilización con atribución; variante exacta de Creative Commons sin confirmar |

### TuBus

| Dato | Estado | Fuente | Observaciones |
| --- | --- | --- | --- |
| Rutas | ✔ | `muniguate_tubus_routes_2025` (ArcGIS) | 8 trazados: 5, 104, 105, 305, 402, 404, 801 y 802 |
| Paradas | ✔ | `muniguate_tubus_stops_2025` (ArcGIS) | 278 paradas: 104 (64), 801 (49), 105 (36), 802 (32), 402 (32), 404 (29), 305 (21), 5 (15) |
| Geometría | ✔ | Capa de rutas | 8 `LineString` continuos |
| Secuencia y sentido | ◐ | Ruteros oficiales en PDF | Solo la ruta 801 está transcrita y validada (47 paradas; la capa tiene 49, con FID 91 y 92 fuera del rutero). La ruta 105 tiene catálogo descargado sin transcribir. La numeración de la capa no es confiable para ordenar |
| Horario | ◐ | Ruteros oficiales | Solo hora de inicio y fin del servicio |
| Frecuencia | ✖ | — | El spike usa un intervalo supuesto de 10–20 min |
| Tarifa | ✖ | — | — |
| Licencia | ◐ | Metadatos del portal | Igual que Transmetro |

### Demás sistemas

| Sistema | Fuente identificada | Situación |
| --- | --- | --- |
| Transurbano | Operador y sistema de pago SIGA | Sin feed abierto; solo información pública de recarga y medios de pago |
| Rutas urbanas concesionadas | Acuerdos municipales y expediente de Guatecompras NOG 27655148 | Documentos con rutas licitadas; sin paradas, geometría ni horarios |
| TransMIO | Municipalidad de Villa Nueva | Sin datos abiertos identificados. **Necesario para el corredor piloto** Metrocentro ↔ UVG |
| Transporte de Mixco | Municipalidad de Mixco | Sin datos abiertos identificados |
| Transpinula | Municipalidad de Santa Catarina Pinula | Sin datos abiertos identificados |
| Extraurbanos | `dgt_open_data_catalog` (DGT) | Catálogo de datos abiertos con tarifas parciales; contenido de rutas por verificar. Fuera del MVP |

## 4. Capas de soporte

| Capa | Fuente | Estado | Uso |
| --- | --- | --- | --- |
| Red peatonal y mapa base | OpenStreetMap | ✔ (ODbL, con obligaciones de atribución) | Caminatas y transbordos |
| Clima y lluvia | `insivumeh_recent_weather_catalog` | ◐ | Ajuste de tiempos (fuera del MVP) |
| Tráfico | Sin fuente abierta | ✖ | Fuera del MVP |
| Incidentes y cierres | Sin fuente abierta | ✖ | Fuera del MVP |

## 5. Brechas priorizadas

Priorizadas por su efecto en el [alcance del MVP](../product/alcance-mvp.md) (Transmetro, TuBus y el corredor piloto).

| Prioridad | Brecha | Sistemas | Efecto si falta | Mitigación mientras tanto |
| --- | --- | --- | --- | --- |
| 1 | Frecuencias y horarios por franja | Transmetro, TuBus | La espera es un supuesto y domina el error | Rangos con supuestos declarados ([ADR-0024](../architecture/adr/0024-confianza-interna-y-estimaciones-como-rangos.md)) |
| 2 | Secuencia y sentido de paradas | TuBus (7 rutas), Transmetro | Sin secuencia no hay grafo de ruteo | Transcribir ruteros PDF y reconciliar como en el spike |
| 3 | Todo el sistema | TransMIO | El corredor piloto no se puede completar | Validación en campo del tramo del corredor |
| 4 | Tiempos de recorrido | Transmetro, TuBus | Tiempos estimados por velocidad supuesta | Velocidad comercial por rangos; observación en campo |
| 5 | Tarifas estructuradas | Todos | Itinerarios sin costo | Tarifa documental cargada a mano con fuente |
| 6 | Licencia exacta | Capas municipales | No se puede publicar el GTFS derivado con certeza | Uso interno hasta confirmar la variante |
| 7 | Todo el sistema | Transurbano, Mixco, Transpinula, concesionadas | Cobertura metropolitana parcial | Fuera del MVP; se incorporan por corredores |

## 6. Mantenimiento

- Las celdas `?` de Transmetro dependen del catálogo oficial en muniguate.com, que responde HTTP 403 a clientes automatizados y está deshabilitado en el recolector (RGT-33). Se resuelven con una descarga manual desde el navegador o con una solicitud a la Municipalidad, nunca evadiendo el bloqueo (ADR-0007).
- Se actualiza al incorporar o refrescar una fuente y al volver a perfilarla con `rutagt-profile`. El [perfil de los datasets municipales](perfil-datasets.md) (RGT-34) detalla campos, códigos y anomalías de las capas de Transmetro y TuBus.
- Cuando la base de datos esté poblada, la matriz se generará desde `provenance.data_source` y la cobertura cargada, en lugar de mantenerse a mano.
