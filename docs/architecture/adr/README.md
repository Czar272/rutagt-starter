# Registro de decisiones de arquitectura

Este directorio contiene los _Architecture Decision Records_ (ADR) de RutaGT: cada decisión significativa sobre la arquitectura, los datos, las tecnologías o el proceso de ingeniería, con su contexto, alternativas, consecuencias y forma de verificación.

El proceso está definido en [ADR-0001](0001-registrar-decisiones-de-arquitectura.md).

## Cómo proponer un ADR

1. Copiar [`template.md`](template.md) como `NNNN-titulo-de-la-decision.md` con el siguiente número disponible.
2. Completarlo con estado `Propuesto` y el ticket de Jira asociado.
3. Agregarlo al índice de este archivo.
4. Abrir un pull request. Al integrarse, el estado pasa a `Aceptado` (o `Rechazado`) en el mismo pull request.

## Estados

| Estado                   | Significado                                                   |
| ------------------------ | ------------------------------------------------------------- |
| Propuesto                | Dirección planificada, pendiente de validación o de su ticket |
| Aceptado                 | Decisión vigente que el proyecto debe cumplir                 |
| Rechazado                | Evaluada y descartada; se conserva como antecedente           |
| Obsoleto                 | Dejó de aplicar sin un reemplazo directo                      |
| Reemplazado por ADR-NNNN | Sustituida por una decisión posterior                         |

## Índice

| ADR                                                                   | Decisión                                                                                      | Estado                   | Fecha      | Tickets                |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------ | ---------- | ---------------------- |
| [0001](0001-registrar-decisiones-de-arquitectura.md)                  | Registrar las decisiones de arquitectura como ADR                                             | Aceptado                 | 2026-11-25 | RGT-110                |
| [0002](0002-postgresql-postgis-como-modelo-canonico.md)               | Usar PostgreSQL con PostGIS como modelo canónico de datos                                     | Aceptado                 | 2026-08-15 | RGT-13, RGT-27         |
| [0003](0003-gtfs-schedule-como-contrato-de-intercambio.md)            | Adoptar GTFS Schedule como contrato de intercambio                                            | Aceptado                 | 2026-08-15 | RGT-12                 |
| [0004](0004-capas-de-datos-inmutables-con-procedencia.md)             | Separar los datos en capas inmutables con procedencia obligatoria                             | Aceptado                 | 2026-08-15 | RGT-14, RGT-16, RGT-25 |
| [0005](0005-python-para-el-pipeline-de-datos.md)                      | Usar Python para el pipeline de datos                                                         | Aceptado                 | 2026-08-15 | RGT-15, RGT-19         |
| [0006](0006-resolver-dinamicamente-items-arcgis.md)                   | Resolver dinámicamente los ítems ArcGIS vigentes                                              | Aceptado                 | 2026-08-15 | RGT-18, RGT-22, RGT-23 |
| [0007](0007-adquirir-datos-solo-por-canales-legitimos.md)             | Adquirir datos solo por canales legítimos                                                     | Aceptado                 | 2026-08-15 | RGT-21, RGT-24         |
| [0008](0008-unidad-de-ruteo-ruta-variante-sentido-calendario.md)      | Modelar la unidad de ruteo como ruta, variante, sentido y calendario                          | Aceptado                 | 2026-08-15 | RGT-13, RGT-44         |
| [0009](0009-configuracion-mediante-variables-de-entorno.md)           | Configurar el sistema mediante variables de entorno                                           | Aceptado                 | 2026-08-18 | RGT-26                 |
| [0010](0010-entorno-local-reproducible-con-docker-compose.md)         | Usar Docker Compose para un entorno local reproducible                                        | Aceptado                 | 2026-08-22 | RGT-27                 |
| [0011](0011-flujo-git-con-ramas-por-ticket.md)                        | Usar un flujo Git basado en main con ramas por ticket                                         | Aceptado                 | 2026-11-25 | RGT-125                |
| [0012](0012-gestion-con-scrum-semanal-en-jira.md)                     | Gestionar el trabajo con Scrum de sprints semanales en Jira                                   | Aceptado                 | 2026-11-25 | RGT-116                |
| [0013](0013-aislar-spikes-del-codigo-productivo.md)                   | Aislar los spikes experimentales del código productivo                                        | Aceptado                 | 2026-08-22 | RGT-115                |
| [0014](0014-opentripplanner-como-motor-de-planificacion.md)           | Usar OpenTripPlanner como motor de planificación con ranking propio                           | Propuesto                | 2026-11-25 | RGT-57 a RGT-60        |
| [0015](0015-monolito-modular-para-el-mvp.md)                          | Construir el MVP como monolito modular                                                        | Aceptado                 | 2026-11-25 | RGT-118, RGT-120       |
| [0016](0016-pwa-como-cliente-principal.md)                            | Usar una PWA como cliente principal del MVP                                                   | Aceptado                 | 2026-11-25 | RGT-70, RGT-121        |
| [0017](0017-confianza-explicita-en-itinerarios.md)                    | Mostrar la incertidumbre y el nivel de confianza en cada itinerario                           | Reemplazado por ADR-0024 | 2026-08-15 | RGT-31, RGT-61, RGT-85 |
| [0018](0018-gtfs-realtime-para-tiempo-real.md)                        | Usar GTFS-Realtime para la información en tiempo real                                         | Propuesto                | 2026-11-25 | RGT-97, RGT-98         |
| [0019](0019-herramientas-de-entorno-y-calidad-de-codigo.md)           | Usar uv, Ruff, mypy y pre-commit con Python 3.12                                              | Aceptado                 | 2026-11-25 | RGT-123                |
| [0020](0020-pytest-y-cobertura-como-estrategia-de-pruebas.md)         | Usar pytest con cobertura mínima y pruebas sin red por defecto                                | Aceptado                 | 2026-11-25 | RGT-124                |
| [0021](0021-integracion-continua-con-github-actions.md)               | Usar GitHub Actions para la integración continua                                              | Aceptado                 | 2026-11-25 | RGT-107                |
| [0022](0022-fastapi-para-la-api.md)                                   | Construir la API de RutaGT con FastAPI                                                        | Aceptado                 | 2026-11-25 | RGT-120                |
| [0023](0023-react-vite-y-maplibre-para-la-pwa.md)                     | Construir la PWA con React, Vite y MapLibre GL JS                                             | Aceptado                 | 2026-11-25 | RGT-121, RGT-70        |
| [0024](0024-confianza-interna-y-estimaciones-como-rangos.md)          | Usar la confianza de los datos internamente y mostrar las estimaciones como rangos            | Aceptado                 | 2026-11-25 | RGT-117, RGT-61        |
| [0025](0025-prettier-y-configuracion-compartida-del-editor.md)        | Formatear con Prettier los archivos que no son Python y compartir la configuración del editor | Aceptado                 | 2026-11-25 | RGT-134                |
| [0026](0026-paquete-rutagt-y-patrones-del-pipeline.md)                | Organizar el código en el paquete `rutagt` con collectors registrados por tipo de fuente      | Aceptado                 | 2026-11-25 | RGT-122                |
| [0027](0027-observabilidad-con-opentelemetry-y-logs-estructurados.md) | Instrumentar con OpenTelemetry y registros estructurados correlacionados                      | Aceptado                 | 2026-11-25 | RGT-109                |

## Decisiones pendientes

Decisiones identificadas que todavía no tienen ADR. Cada una se registrará al resolverse su ticket.

| Decisión                                        | Ticket  |
| ----------------------------------------------- | ------- |
| Herramienta de migraciones del esquema canónico | RGT-29  |
| Niveles de confianza y calidad de datos         | RGT-31  |
| Política de versionado de datasets              | RGT-32  |
| Función de ranking de itinerarios               | RGT-60  |
| Licencia del código y de los datos publicados   | RGT-111 |
| Estrategia de seguridad base                    | RGT-113 |

## Nota sobre fechas

Los ADR-0002 a ADR-0010, ADR-0013 y ADR-0017 documentan decisiones tomadas antes de establecer este registro. Su fecha corresponde a la decisión original, respaldada por los tickets de Jira y el historial de commits indicados; su redacción formal se realizó el 2026-11-25 (RGT-119).
