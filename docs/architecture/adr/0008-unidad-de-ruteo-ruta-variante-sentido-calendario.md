# ADR-0008: Modelar la unidad de ruteo como ruta, variante, sentido y calendario

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-08-15 |
| Decisores   | @Czar272   |
| Tickets     | RGT-13, RGT-44 |
| Reemplaza a | —          |

## Contexto

En Guatemala, una misma «ruta» comercial puede tener variantes (cortas, expresas, por horario), recorridos distintos en cada sentido, circuitos y horarios diferentes entre días laborales y fines de semana. Las capas municipales asocian paradas a un código de ruta (`Codigoruta`), pero no a un sentido ni a una secuencia. Si la unidad de planificación fuera solo la línea, el sistema podría indicar abordar en el sentido equivocado o en un horario sin servicio.

## Decisión

La unidad mínima que el sistema usa para planificar viajes es la combinación **ruta + variante + sentido + calendario**:

- `route`: la línea comercial u oficial.
- `route_pattern`: una variante con su sentido (`direction_id`), forma (`shape`) y secuencia de paradas (`pattern_stop`).
- `service_calendar` / `service_exception`: los días y fechas de operación.
- `trip` y `frequency`: los viajes concretos o sus intervalos.

Ninguna parada se asocia a una ruta sin indicar el patrón y la posición en la secuencia.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Ruta como unidad | Coincide con los datos municipales actuales | No distingue sentido ni variantes; produce instrucciones erróneas | Inseguro para el usuario |
| Ordenar paradas por proximidad a la línea | Automatizable | Falla en circuitos, retornos y vías compartidas | Comprobado como insuficiente |

## Consecuencias

### Positivas

- Instrucciones correctas de sentido, parada de abordaje y descenso.
- Compatible con el modelo de GTFS (`trips`, `stop_times`, `direction_id`, `shape_id`).

### Negativas y riesgos

- Los datos abiertos actuales no contienen secuencias ni sentidos; deben obtenerse de ruteros oficiales, solicitudes o campo (RGT-43, RGT-49, RGT-115).

## Verificación

- `database/schema/canonical.sql` define `route_pattern`, `pattern_stop`, `service_calendar`, `trip` y `frequency`.

## Referencias

- `README.md`, sección «Principios de diseño».
- `docs/data/plan-producto-y-datos.md`, secciones 3 y 4.5.
