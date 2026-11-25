# ADR-0027: Instrumentar con OpenTelemetry y registros estructurados correlacionados

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-109    |
| Reemplaza a | —          |

## Contexto

RutaGT tendrá varios procesos que deben observarse en conjunto: el pipeline de datos que se ejecuta por lotes, la API ([ADR-0022](0022-fastapi-para-la-api.md)), PostGIS y OpenTripPlanner ([ADR-0014](0014-opentripplanner-como-motor-de-planificacion.md)). El criterio C6 del [alcance del MVP](../../product/alcance-mvp.md) exige p95 < 3 s en planificación, y la calidad del producto depende de que las fuentes de datos se mantengan actualizadas. Hasta ahora el pipeline solo emitía mensajes de texto sin identificador de ejecución, lo que impedía correlacionar registros, manifiestos y procedencia, o enviarlos a una plataforma de análisis.

Las ubicaciones de origen y destino que consulten las personas son datos sensibles que no deben quedar en la telemetría.

## Decisión

- **Estándar:** la instrumentación de métricas y trazas usa **OpenTelemetry** con exportación **OTLP**; la plataforma de almacenamiento y visualización se elige con el entorno de producción.
- **Registros:** `logging` estándar con dos formatos seleccionables con `RUTAGT_LOG_FORMAT`: `text` para desarrollo y `json` (un objeto por línea) para producción.
- **Correlación:** un contexto de registro (`log_context`) agrega identificadores a todos los registros de una operación: `run_id` y `source_id` en el pipeline; `request_id`, `trace_id` y `span_id` en la API.
- **Pipeline:** cada ejecución registra en `run_manifest.json` su `run_id`, inicio, fin, duración total y por fuente, y un resumen.
- **Objetivos de servicio:** latencia de planificación p95 < 3 s, disponibilidad de la API de 99,5 % mensual y frescura de datos automatizables ≤ 7 días, con las alertas iniciales definidas en el documento de observabilidad.
- **Privacidad:** no se registran ubicaciones exactas, direcciones escritas, IP completas ni secretos.

El detalle está en [`docs/architecture/observability.md`](../observability.md).

## Alternativas consideradas

| Alternativa                                              | Ventajas             | Desventajas                                   | Motivo de descarte                                                    |
| -------------------------------------------------------- | -------------------- | --------------------------------------------- | --------------------------------------------------------------------- |
| SDK de un proveedor (Datadog, New Relic)                 | Integración completa | Acoplamiento y costo por volumen              | OTLP permite cambiar de plataforma sin reinstrumentar                 |
| Solo registros de texto                                  | Simplicidad          | Sin métricas, trazas ni análisis automatizado | Insuficiente para verificar C6 y la frescura de datos                 |
| Librería de logging estructurado de terceros (structlog) | API cómoda           | Dependencia adicional en el núcleo            | `logging` con un formateador JSON cubre la necesidad actual           |
| Prometheus con `/metrics` sin OpenTelemetry              | Muy extendido        | Solo métricas; trazas por separado            | OpenTelemetry unifica métricas y trazas y puede exportar a Prometheus |

## Consecuencias

### Positivas

- Registros, manifiestos y, más adelante, métricas y trazas comparten identificadores de correlación.
- La plataforma de observabilidad puede elegirse o cambiarse sin modificar el código.
- Los objetivos de servicio quedan definidos antes de construir la API.

### Negativas y riesgos

- OpenTelemetry agrega dependencias y configuración a la API.
- Los objetivos y umbrales de alerta son iniciales y deben calibrarse con datos reales.

## Verificación

- `RUTAGT_LOG_FORMAT=json uv run rutagt-collect fetch --all` emite un objeto JSON por línea con `run_id` y `source_id`.
- `run_manifest.json` incluye `run_id`, `started_at`, `finished_at`, `duration_seconds` y `summary`.
- `tests/core/test_logging.py` y `tests/pipeline/test_cli.py` verifican el formato y la correlación.

## Referencias

- [OpenTelemetry](https://opentelemetry.io/), [convenciones semánticas HTTP](https://opentelemetry.io/docs/specs/semconv/http/).
- [Google SRE — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/).
- [`docs/architecture/observability.md`](../observability.md).
