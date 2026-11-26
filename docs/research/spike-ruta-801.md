# Informe del spike de ruteo: ruta 801 de TuBus

| Campo  | Valor                                                                                                                                                 |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ticket | [RGT-115](https://pablo2003cesar.atlassian.net/browse/RGT-115) (subtareas RGT-126 a RGT-133 y RGT-135)                                                |
| Sprint | 4 — Spike ruta 801                                                                                                                                    |
| Fecha  | 2026-11-25                                                                                                                                            |
| Código | [`prototype/routing/`](../../prototype/routing/README.md) (experimental, [ADR-0013](../architecture/adr/0013-aislar-spikes-del-codigo-productivo.md)) |
| Estado | Concluido                                                                                                                                             |

## 1. Resumen ejecutivo

El spike tenía dos objetivos: determinar **hasta dónde se puede construir un itinerario con los datos abiertos disponibles** y **qué datos faltan** para hacerlo bien.

**Resultado técnico.** Con la capa abierta de paradas, el trazado oficial y la transcripción del rutero en PDF fue posible reconstruir la ruta 801 completa: 47 paradas en orden, separadas por sentido, sobre un circuito de 19,9 km. Sobre esa red se construyó un grafo dirigido y un planificador que resuelve correctamente consultas origen–destino, incluida la elección del lado correcto de la calle. **La capa abierta por sí sola no basta**: no tiene secuencia ni sentido, y su numeración contiene errores que llevan a asignaciones incorrectas si se confía en ella.

**Datos faltantes.** Lo que impide recomendar viajes confiables no es el algoritmo, sino la falta de datos operativos: **frecuencias, tiempos de recorrido, horarios por franja, tarifas y transbordos**. También se identificaron errores concretos en la capa municipal que conviene reportar.

| Pregunta del spike                                         | Respuesta                                                                               |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| ¿Se puede reconstruir la secuencia de paradas por sentido? | Sí, combinando el rutero PDF con el trazado; no con la capa sola                        |
| ¿Es confiable la capa abierta de paradas?                  | En ubicación, en general sí; en numeración y direcciones, no                            |
| ¿Se puede planificar un viaje origen–destino?              | Sí, en una sola ruta, con tiempos como rangos basados en supuestos                      |
| ¿Qué falta para recomendaciones confiables?                | Frecuencias, tiempos de recorrido, horarios, tarifas, transbordos y validación en campo |

## 2. Fuentes y método

| Fuente                                                        | Uso                                                                         | Calidad asignada          |
| ------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------- |
| Rutero oficial de la ruta 801, versión 4 (PDF, marzo de 2025) | Secuencia, código, dirección y zona de las 47 paradas; horarios de servicio | `official`                |
| Capa «Paradas TuBus 2025» (ArcGIS, DIGM)                      | Ubicación de las paradas                                                    | `probable` / `unverified` |
| Capa «Rutas TuBus 2025» (ArcGIS, DIGM)                        | Trazado del recorrido                                                       | `official`                |

Pasos, cada uno reproducible con un script del prototipo:

| Paso                                             | Subtarea         | Resultado                                                                                |
| ------------------------------------------------ | ---------------- | ---------------------------------------------------------------------------------------- |
| Auditoría de candidatos                          | RGT-126          | 21 paradas a revisar y alertas por número, orden, distancia y registros sobrantes        |
| Validación de la transcripción y revisión manual | RGT-127          | Transcripción validada contra el PDF (47/47); correspondencia revisada parada por parada |
| Reconciliación ordenada                          | RGT-128          | Algoritmo que reproduce la revisión manual sin intervención (47/47)                      |
| GeoJSON enriquecido                              | RGT-129          | Red con procedencia, discrepancias y calidad por atributo                                |
| Mapa interactivo y prueba e2e                    | RGT-130, RGT-135 | Visualización con MapLibre verificada en navegador real                                  |
| Grafo dirigido                                   | RGT-131          | Red por sentido con distancias y tiempos como rangos                                     |
| Consultas origen–destino                         | RGT-132          | 5 consultas con el resultado esperado, evaluación y limitaciones                         |

## 3. Hallazgos de calidad de datos

### 3.1 La transcripción del rutero es correcta

Las 47 paradas transcritas coinciden con la tabla del PDF oficial en código y zona, con similitud de dirección ≥ 0,97. El checksum del documento quedó registrado en la procedencia.

### 3.2 Errores en la capa «Paradas TuBus 2025»

| Hallazgo                                                                                         | Registros                                                                                                             | Efecto                                                                  |
| ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Numeración corrida en +1**: el nombre de cada registro indica el número de la parada siguiente | #095 a #104 (FID 208, 93, 94, 95, 97, 98, 99, 100, 101)                                                               | Un algoritmo que confíe en el número asigna mal 9 de las 47 paradas     |
| Número mal digitado: «Parada 947» en lugar de 094                                                | FID 90                                                                                                                | Parada no identificable por su número                                   |
| Número repetido: dos registros «Parada 105»                                                      | FID 101 y FID 102                                                                                                     | Ambigüedad                                                              |
| **Dos paradas que no figuran en el rutero vigente**                                              | FID 91 (Calzada San Juan y 7a av., «Funerales Reforma») y FID 92 (Calzada San Juan y 9a av. «B», «C.C. Promo Centro») | Paradas posiblemente retiradas o de otra ruta; se excluyeron del modelo |
| Direcciones desplazadas una cuadra o mal escritas                                                | #073 a #077, #080, #098                                                                                               | Requieren validación en campo                                           |
| Registros con nombre descriptivo en lugar de número                                              | p. ej. «Monumento a la Madre», «Trebol zona 8»                                                                        | La capa mezcla nombres y números                                        |

La ubicación geográfica es consistente: los 49 registros están a menos de 13 m del trazado oficial y siguen su orden.

### 3.3 Calidad resultante del modelo

| Atributo                                           | Nivel                    |
| -------------------------------------------------- | ------------------------ |
| Secuencia, código y dirección de las 47 paradas    | `official`               |
| Ubicación de 33 paradas (capa y rutero concuerdan) | `probable`               |
| Ubicación de 14 paradas (capa y rutero discrepan)  | `unverified`             |
| Paradas con al menos una discrepancia              | 23                       |
| Tiempos de viaje y espera                          | `unverified` (supuestos) |

## 4. Hasta dónde se llega con datos abiertos

| Capacidad                                    | Estado          | Condición                                                           |
| -------------------------------------------- | --------------- | ------------------------------------------------------------------- |
| Mapa de la ruta y sus paradas                | ✔ Lograda       | —                                                                   |
| Secuencia de paradas por sentido             | ✔ Lograda       | Requiere el rutero PDF; la capa no la contiene                      |
| Grafo dirigido con distancias                | ✔ Lograda       | Distancias medidas sobre el trazado oficial                         |
| Planificación origen–destino en una ruta     | ✔ Lograda       | Elige correctamente el sentido y el lado de la calle                |
| Tiempos de viaje                             | ⚠ Estimados     | Velocidad comercial supuesta de 12–18 km/h                          |
| Tiempo de espera                             | ⚠ Estimado      | Intervalo supuesto de 10–20 min                                     |
| Horarios por franja y día                    | ✖ No disponible | Solo hay ventanas de servicio de inicio y fin                       |
| Transbordos con otras rutas y con Transmetro | ✖ No modelado   | El rutero indica estaciones cercanas a pie, sin datos estructurados |
| Tarifas                                      | ✖ No disponible | —                                                                   |
| Caminata real                                | ✖ No modelada   | Requiere la red peatonal de OpenStreetMap                           |

Resultados de las consultas de ejemplo (supuestos indicados arriba):

| Consulta                                            | Mejor opción         | Tiempo    |
| --------------------------------------------------- | -------------------- | --------- |
| Parque Kaminaljuyú → Parque de la Industria         | Ruta 801 #075 → #086 | 31–46 min |
| Terminal zona 9 → Colonia Bethania                  | Ruta 801 #087 → #106 | 44–65 min |
| Ciudad de Plata (lado del regreso) → Kjell Laugerud | Ruta 801 #101 → #105 | 15–23 min |
| Trayecto corto en Bethania                          | Caminar              | 6–8 min   |
| Punto fuera del recorrido                           | Sin itinerario       | —         |

## 5. Datos faltantes, priorizados

| Prioridad | Dato                                                                                        | Por qué se necesita                                                 | Fuente                            |
| --------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------- |
| Alta      | Frecuencias o intervalos por franja horaria y día                                           | Sin ellos la espera es un supuesto y domina el error del itinerario | Municipalidad (EMT/STP)           |
| Alta      | Tiempos de recorrido entre paradas o por tramo                                              | Reemplazar la velocidad supuesta                                    | Municipalidad (EMT/STP)           |
| Alta      | Secuencia oficial de paradas por sentido en formato tabular, con identificadores de la capa | Evitar la reconciliación manual en cada ruta                        | Municipalidad (DMU/DIGM)          |
| Alta      | Confirmación de las paradas FID 91 y FID 92 (Calzada San Juan)                              | Saber si el rutero está incompleto o la capa desactualizada         | Municipalidad (DMU)               |
| Media     | Corrección de la numeración de la capa (#094 a #105)                                        | Que la capa sea usable sin el rutero                                | Municipalidad (DIGM)              |
| Media     | Tarifas y medios de pago vigentes                                                           | Costo del itinerario                                                | Municipalidad                     |
| Media     | Transbordos permitidos y conexiones con Transmetro                                          | Itinerarios con más de una ruta                                     | Municipalidad (EMT)               |
| Media     | Licencia exacta de las capas (variante de Creative Commons)                                 | Publicar datos derivados                                            | Municipalidad (DIGM)              |
| Baja      | Posición de vehículos (AVL) o GTFS-Realtime                                                 | Tiempo real (fuera del MVP)                                         | Municipalidad (Centro de Control) |

## 6. Recomendaciones para el código productivo

| Recomendación                                                                                                                                                                                                                  | Ticket del backlog     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------- |
| Normalizar paradas por **posición sobre el trazado y alineación ordenada con la secuencia oficial**, no por el número en el nombre; reimplementar la reconciliación del spike en `rutagt.pipeline.normalizers` con sus pruebas | RGT-35, RGT-37, RGT-43 |
| Comparar direcciones con **similitud que distinga números de vía**                                                                                                                                                             | RGT-37                 |
| Conservar el **número del nombre solo como alerta de calidad**                                                                                                                                                                 | RGT-37, RGT-40         |
| Modelar **sentido y terminal** explícitamente y el cierre de circuito como parte del patrón                                                                                                                                    | RGT-43, RGT-44         |
| Tratar tiempos y esperas como **rangos con supuestos declarados** hasta tener datos oficiales                                                                                                                                  | RGT-45, RGT-46, RGT-61 |
| Usar la **lista de 14 paradas `unverified`** como plan de validación en campo                                                                                                                                                  | RGT-81                 |
| Incorporar la **red peatonal de OpenStreetMap** para caminatas y transbordos                                                                                                                                                   | RGT-48, RGT-57         |
| Aprovechar los minutos a pie a estaciones de Transmetro indicados en el rutero como primera fuente de transbordos                                                                                                              | RGT-48                 |

[ADR-0014](../architecture/adr/0014-opentripplanner-como-motor-de-planificacion.md) (OpenTripPlanner) se mantiene como propuesto: el spike confirma que el valor diferencial está en la calidad de los datos y en el ranking, no en el algoritmo de búsqueda, lo que refuerza usar un motor existente.

## 7. Limitaciones del spike

- Cubre una sola ruta; la estrategia debe probarse en otras rutas de TuBus y en Transmetro.
- El método depende de contar con el rutero de cada ruta; sin él no hay secuencia confiable.
- Los tiempos son estimaciones y no se validaron con viajes reales.
- No hubo validación en campo de ninguna parada.
- El código es experimental y no se integra al paquete `rutagt`; se reimplementará en los tickets indicados.

## 8. Artefactos

| Artefacto                                                                                                            | Descripción                                |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| [`data/route_801_official.json`](../../prototype/routing/data/route_801_official.json)                               | Transcripción validada del rutero          |
| [`data/route_801_reviewed_mapping.json`](../../prototype/routing/data/route_801_reviewed_mapping.json)               | Correspondencia revisada parada → registro |
| [`output/route_801_candidate_audit.md`](../../prototype/routing/output/route_801_candidate_audit.md)                 | Auditoría de candidatos                    |
| [`output/route_801_reviewed_mapping.md`](../../prototype/routing/output/route_801_reviewed_mapping.md)               | Reporte de la revisión                     |
| [`output/route_801_sequence_reconciliation.md`](../../prototype/routing/output/route_801_sequence_reconciliation.md) | Resultado del reconciliador ordenado       |
| [`output/route_801_enriched.geojson`](../../prototype/routing/output/route_801_enriched.geojson)                     | Red enriquecida con procedencia y calidad  |
| [`output/route_801_map.html`](../../prototype/routing/output/route_801_map.html)                                     | Mapa interactivo                           |
| [`output/route_801_graph.json`](../../prototype/routing/output/route_801_graph.json)                                 | Grafo dirigido                             |
| [`output/route_801_od_queries.md`](../../prototype/routing/output/route_801_od_queries.md)                           | Consultas origen–destino                   |
