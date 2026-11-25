# ADR-0014: Usar OpenTripPlanner como motor de planificación con ranking propio

| Campo       | Valor                           |
| ----------- | ------------------------------- |
| Estado      | Propuesto                       |
| Fecha       | 2026-11-25                      |
| Decisores   | @Czar272                        |
| Tickets     | RGT-57, RGT-58, RGT-59, RGT-60  |
| Reemplaza a | —                               |

## Contexto

RutaGT necesita calcular itinerarios multimodales (caminata + transporte público con transbordos) sobre la red vial y los datos GTFS. Implementar desde cero un algoritmo de planificación con calendarios, frecuencias, transbordos y caminata sobre la red peatonal es costoso y propenso a errores. A la vez, el producto necesita un criterio propio para recomendar la «mejor» opción según el contexto guatemalteco: incertidumbre de los datos, seguridad de los transbordos, costo y accesibilidad.

## Decisión propuesta

- Usar **OpenTripPlanner (OTP)** como motor de planificación, alimentado por el feed GTFS de RutaGT ([ADR-0003](0003-gtfs-schedule-como-contrato-de-intercambio.md)) y un extracto de **OpenStreetMap** del área piloto.
- OTP genera alternativas; RutaGT aplica una **función de ranking propia** sobre ellas:

  `Score = f(T, E, C, B, A, U, $)` — tiempo de viaje, espera, caminata, transbordos, accesibilidad, incertidumbre y costo monetario.

- La API de RutaGT consume OTP; los clientes nunca acceden a OTP directamente.

Esta decisión se confirmará o reemplazará al desplegar OTP local y probar itinerarios reales (Sprint 9 - Routing local). La fórmula y los pesos del ranking se definirán en RGT-60 con su propio ADR.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Estado |
| --- | --- | --- | --- |
| Algoritmo propio (RAPTOR/CSA) | Control total | Alto costo y riesgo de errores | Descartada para el MVP |
| Grafo propio sobre PostGIS/pgRouting | Integrado a la base | No maneja horarios ni frecuencias de forma nativa | Útil solo para spikes |
| APIs comerciales (Google, Moovit) | Sin operación | Costo, dependencia y datos de terceros | Incompatible con [ADR-0007](0007-adquirir-datos-solo-por-canales-legitimos.md) |
| R5 / MOTIS | Alternativas abiertas | Menor adopción para itinerarios de usuario final | Por evaluar si OTP no cumple |

## Consecuencias esperadas

### Positivas

- Motor maduro, abierto y usado por agencias de transporte en el mundo.
- El valor diferencial de RutaGT se concentra en los datos y en el ranking.

### Negativas y riesgos

- OTP requiere memoria considerable y una JVM; impacta el costo de infraestructura.
- La calidad de los itinerarios depende de la calidad del GTFS y del extracto OSM.

## Verificación

- OTP local desplegado con el GTFS de RutaGT (RGT-58).
- Suite de rutas doradas que compara itinerarios esperados contra los generados (RGT-62).

## Referencias

- [OpenTripPlanner](https://www.opentripplanner.org/).
- `docs/data/plan-producto-y-datos.md`, secciones 7 y 9.
