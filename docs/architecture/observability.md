# Observabilidad

| Campo   | Valor                                                                         |
| ------- | ----------------------------------------------------------------------------- |
| Versión | 1.0                                                                           |
| Fecha   | 2026-11-25                                                                    |
| Ticket  | RGT-109                                                                       |
| ADR     | [ADR-0027](adr/0027-observabilidad-con-opentelemetry-y-logs-estructurados.md) |

Este documento define cómo RutaGT registra, mide y traza su funcionamiento para detectar fallas, verificar los objetivos de servicio y diagnosticar problemas, tanto en el pipeline de datos como en la API y el motor de planificación. Las partes marcadas como _implementado_ ya existen en el repositorio; el resto se implementa junto con cada componente.

## 1. Principios

1. **Estándares abiertos:** instrumentación con [OpenTelemetry](https://opentelemetry.io/) y exportación OTLP, sin acoplarse a un proveedor.
2. **Correlación:** todo registro, métrica y traza de una misma operación comparte un identificador (`run_id` en el pipeline, `request_id` y `trace_id` en la API).
3. **Estructura:** los registros son eventos con campos, no texto libre; en producción se emiten como JSON.
4. **Privacidad por diseño:** nunca se registran datos personales ni ubicaciones exactas de las personas usuarias (ver sección 7).
5. **Mínimo útil:** se mide lo que sostiene los objetivos de servicio y la calidad de datos; no se recolecta telemetría sin un uso definido.

## 2. Registros (logs)

| Aspecto     | Definición                                                         | Estado       |
| ----------- | ------------------------------------------------------------------ | ------------ |
| Biblioteca  | `logging` estándar de Python, un logger por módulo                 | Implementado |
| Formatos    | `text` (desarrollo) y `json` (producción), con `RUTAGT_LOG_FORMAT` | Implementado |
| Nivel       | `RUTAGT_LOG_LEVEL` (por defecto `INFO`)                            | Implementado |
| Destino     | Salida de error estándar; el entorno de ejecución los recolecta    | Implementado |
| Correlación | `log_context(...)` agrega campos a todos los registros del bloque  | Implementado |

Campos de cada registro JSON:

| Campo                               | Descripción                                     | Ejemplo                                        |
| ----------------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| `timestamp`                         | Fecha y hora UTC con milisegundos               | `2026-11-25T15:04:05.123+00:00`                |
| `level`                             | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO`                                         |
| `logger`                            | Módulo que emite el registro                    | `rutagt.pipeline.cli`                          |
| `message`                           | Mensaje legible                                 | `OK muniguate_tubus_stops_2025: 278 registros` |
| `service`                           | Servicio emisor                                 | `rutagt`                                       |
| `run_id`                            | Ejecución del pipeline                          | `9f1c…`                                        |
| `source_id`                         | Fuente en proceso                               | `muniguate_tubus_stops_2025`                   |
| `request_id`, `trace_id`, `span_id` | Petición de la API y su traza (Sprint 10)       | —                                              |
| `exception`                         | Traza de la excepción, si existe                | —                                              |

Uso de niveles:

- `ERROR`: una operación falló y requiere atención (fuente caída, error inesperado).
- `WARNING`: degradación recuperable (reintento HTTP, advertencia de calidad).
- `INFO`: hitos de una operación (inicio, fin, resultados).
- `DEBUG`: detalle para diagnóstico; desactivado en producción.

## 3. Métricas

Las métricas siguen las convenciones semánticas de OpenTelemetry y se exportan por OTLP.

### Pipeline de datos

Hasta disponer de una plataforma de métricas, cada ejecución queda registrada en `run_manifest.json` (_implementado_: `run_id`, inicio, fin, duración total y por fuente, resumen y resultados).

| Métrica                                   | Tipo           | Etiquetas                 | Uso                                                     |
| ----------------------------------------- | -------------- | ------------------------- | ------------------------------------------------------- |
| `rutagt.pipeline.run.duration`            | Histograma (s) | `stage`                   | Detectar ejecuciones lentas                             |
| `rutagt.pipeline.source.duration`         | Histograma (s) | `source_id`, `outcome`    | Detectar fuentes degradadas                             |
| `rutagt.pipeline.source.records`          | Gauge          | `source_id`               | Detectar cambios bruscos en el volumen de datos         |
| `rutagt.pipeline.source.failures`         | Contador       | `source_id`, `error_type` | Alertar fuentes caídas                                  |
| `rutagt.pipeline.source.quality_warnings` | Gauge          | `source_id`               | Seguir la calidad de cada fuente                        |
| `rutagt.data.freshness`                   | Gauge (s)      | `source_id`               | Antigüedad del último dato válido; objetivo de frescura |

### API (Sprint 10)

Métricas RED (_Rate, Errors, Duration_) por ruta, generadas por la instrumentación de FastAPI:

| Métrica                        | Tipo           | Etiquetas                                                        |
| ------------------------------ | -------------- | ---------------------------------------------------------------- |
| `http.server.request.duration` | Histograma (s) | `http.route`, `http.request.method`, `http.response.status_code` |
| `http.server.active_requests`  | UpDownCounter  | `http.route`                                                     |
| `rutagt.plan.itineraries`      | Histograma     | número de alternativas devueltas                                 |
| `rutagt.plan.no_result`        | Contador       | consultas sin itinerario (sin coordenadas)                       |
| `rutagt.otp.request.duration`  | Histograma (s) | `outcome`                                                        |

## 4. Trazas (Sprint 10)

- La API se instrumenta con OpenTelemetry para FastAPI, SQLAlchemy y HTTPX.
- Una consulta de planificación produce una traza con tramos para la API, PostGIS y OpenTripPlanner, que permite ver dónde se consume el tiempo del criterio C6 (p95 < 3 s).
- El `trace_id` se incluye en los registros y se devuelve en el encabezado de respuesta para soporte.
- Muestreo: 100 % de las trazas con error y 10 % de las exitosas, ajustable por configuración.

## 5. Verificaciones de salud (Sprint 10)

| Endpoint            | Comprueba                                                               | Uso                 |
| ------------------- | ----------------------------------------------------------------------- | ------------------- |
| `GET /health/live`  | El proceso responde                                                     | Reinicio automático |
| `GET /health/ready` | Conexión a PostGIS y a OpenTripPlanner, y versión del feed GTFS cargado | Recibir tráfico     |

## 6. Objetivos de servicio y alertas

| Objetivo (SLO)                   | Meta                                                           | Medición                                  |
| -------------------------------- | -------------------------------------------------------------- | ----------------------------------------- |
| Latencia de planificación        | p95 < 3 s (criterio C6 del MVP)                                | `http.server.request.duration` de `/plan` |
| Disponibilidad de la API         | 99,5 % mensual                                                 | Peticiones exitosas / totales             |
| Frescura de datos automatizables | Cada fuente recolectada con éxito al menos una vez cada 7 días | `rutagt.data.freshness`                   |

Alertas iniciales:

| Alerta                               | Condición                                                    | Severidad |
| ------------------------------------ | ------------------------------------------------------------ | --------- |
| Fuente caída                         | La misma fuente falla en 2 ejecuciones consecutivas          | Media     |
| Datos desactualizados                | Frescura de una fuente > 7 días                              | Media     |
| Cambio brusco de volumen             | Registros de una fuente varían más de 20 % entre ejecuciones | Media     |
| Latencia degradada                   | p95 de `/plan` > 3 s durante 15 min                          | Alta      |
| Errores de la API                    | Tasa de respuestas 5xx > 2 % durante 5 min                   | Alta      |
| Motor de planificación no disponible | `/health/ready` falla durante 2 min                          | Crítica   |

## 7. Privacidad y retención

- **Ubicaciones:** el origen y el destino de una consulta no se registran con precisión. En registros y métricas solo se admiten coordenadas redondeadas a 2 decimales (≈ 1 km) o la zona; nunca direcciones escritas por la persona.
- **Identificadores:** no se registran direcciones IP completas, identificadores de dispositivo ni datos de cuentas. La política completa se define en RGT-112.
- **Secretos:** nunca se registran credenciales, tokens ni cadenas de conexión.
- **Retención:** registros 30 días; trazas 7 días; métricas agregadas 13 meses; manifiestos del pipeline se conservan junto a los datos que describen.

## 8. Plataforma

La instrumentación es independiente de la plataforma gracias a OTLP. La plataforma concreta (por ejemplo, Grafana con Loki, Prometheus y Tempo, gestionada o autoalojada) se elegirá junto con el entorno de producción, antes del Sprint 10, en función de costo y operación. En desarrollo basta con los registros en consola y los manifiestos.

## 9. Implementación por etapas

| Etapa               | Entregable                                                                           |
| ------------------- | ------------------------------------------------------------------------------------ |
| Sprint 3 (actual)   | Logs `text`/`json`, contexto de correlación, `run_id` y duraciones en el manifiesto  |
| Sprint 5–8          | Métricas del pipeline y frescura de datos por fuente                                 |
| Sprint 10           | OpenTelemetry en la API: trazas, métricas RED, `request_id`, verificaciones de salud |
| Antes de producción | Plataforma de observabilidad, tableros y alertas                                     |
