# ADR-0015: Construir el MVP como monolito modular

| Campo       | Valor            |
| ----------- | ---------------- |
| Estado      | Propuesto        |
| Fecha       | 2026-11-25       |
| Decisores   | @Czar272         |
| Tickets     | RGT-118, RGT-120 |
| Reemplaza a | —                |

## Contexto

El sistema tiene responsabilidades diferenciadas: pipeline de datos, base canónica, motor de ruteo, API y PWA. Dividirlas desde el inicio en microservicios multiplicaría la operación (despliegues, observabilidad, comunicación entre servicios) para un equipo reducido y un volumen de uso inicial bajo.

## Decisión propuesta

El MVP se compone de pocos elementos desplegables con límites internos claros:

| Elemento | Responsabilidad |
| --- | --- |
| Pipeline de datos (proceso por lotes) | Recolección, normalización, validación y exportación GTFS |
| PostgreSQL + PostGIS | Modelo canónico |
| OpenTripPlanner | Planificación de itinerarios |
| API RutaGT (monolito modular) | Consultas, ranking y composición de itinerarios |
| PWA | Interfaz de usuario |

Dentro de la API, los módulos (paradas, rutas, lugares, planificación) se separan por dominio y se comunican mediante interfaces internas, de modo que puedan extraerse como servicios si la escala lo justifica.

Se confirmará con la vista de arquitectura (RGT-118) y la selección de tecnología del backend (RGT-120).

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Estado |
| --- | --- | --- | --- |
| Microservicios desde el inicio | Escalado independiente | Complejidad operativa desproporcionada | Descartada para el MVP |
| Monolito sin módulos | Más simple al principio | Acoplamiento que dificulta crecer | Descartada |

## Consecuencias esperadas

### Positivas

- Menor costo de operación y despliegue.
- Evolución gradual hacia servicios cuando haya evidencia de necesidad.

### Negativas y riesgos

- Requiere disciplina para respetar los límites entre módulos dentro de un mismo despliegue.

## Verificación

- La vista de arquitectura documenta los elementos y sus interfaces (RGT-118).
- La estructura del backend refleja módulos por dominio (RGT-120).

## Referencias

- `docs/data/plan-producto-y-datos.md`, sección 9.
