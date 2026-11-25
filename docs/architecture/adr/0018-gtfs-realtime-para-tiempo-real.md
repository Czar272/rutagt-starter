# ADR-0018: Usar GTFS-Realtime para la información en tiempo real

| Campo       | Valor          |
| ----------- | -------------- |
| Estado      | Propuesto      |
| Fecha       | 2026-11-25     |
| Decisores   | @Czar272       |
| Tickets     | RGT-97, RGT-98 |
| Reemplaza a | —              |

## Contexto

La fase de tiempo real incorporará posiciones de vehículos, alertas de servicio y predicciones de llegada. Los operadores podrían entregar datos AVL/GPS en formatos propietarios distintos. Sin un formato común, cada integración requeriría lógica específica en el motor de ruteo, la API y la PWA.

## Decisión propuesta

- Usar **GTFS-Realtime** (`VehiclePositions`, `TripUpdates`, `ServiceAlerts`) como formato interno y de intercambio de la información en tiempo real, consistente con [ADR-0003](0003-gtfs-schedule-como-contrato-de-intercambio.md).
- Los datos AVL de cada operador se convierten a GTFS-Realtime en un adaptador de ingesta.
- Las observaciones se almacenan en `vehicle_position` y `stop_event` para construir históricos y modelos de ETA.
- Las predicciones se distinguen siempre de los horarios programados ([ADR-0017](0017-confianza-explicita-en-itinerarios.md)).

Esta decisión se confirmará al inventariar la disponibilidad real de AVL por operador (RGT-97).

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Estado |
| --- | --- | --- | --- |
| Formatos propietarios por operador | Sin conversión | Integraciones acopladas a cada proveedor | Descartada |
| SIRI | Estándar europeo completo | Poco soporte regional y en OTP para este caso | Descartada |

## Consecuencias esperadas

### Positivas

- OpenTripPlanner consume GTFS-Realtime de forma nativa.
- Nuevos operadores se integran escribiendo solo su adaptador.

### Negativas y riesgos

- Depende de acuerdos con operadores para obtener datos AVL.

## Verificación

- Modelo de ingestión documentado (RGT-98) y adaptador por operador con pruebas.

## Referencias

- [GTFS Realtime Reference](https://gtfs.org/documentation/realtime/reference/).
- `docs/data/plan-producto-y-datos.md`, sección 10, fase 4.
