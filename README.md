# RutaGT

[![CI](https://github.com/Czar272/rutagt-starter/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Czar272/rutagt-starter/actions/workflows/ci.yml)

**Rutas de transporte público de Guatemala** — _Tu bus, tu ruta, a tiempo._

RutaGT es una plataforma de planificación de viajes en transporte público multimodal para el Área Metropolitana de Guatemala. Su objetivo es que cualquier persona indique dónde está y a dónde quiere llegar, y reciba recomendaciones claras, accesibles y verificables: qué transporte usar, dónde abordarlo, dónde bajarse y cómo completar el viaje.

La información del transporte público guatemalteco está fragmentada y rara vez disponible en formatos estructurados. RutaGT la recolecta desde fuentes oficiales, la normaliza conservando su procedencia y la transforma en itinerarios con un nivel de confianza explícito.

## Contenido

- [Estado actual](#estado-actual)
- [Arquitectura](#arquitectura)
- [Tecnologías](#tecnologías)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Requisitos](#requisitos)
- [Configuración local](#configuración-local)
- [Uso](#uso)
- [Pruebas](#pruebas)
- [Principios de diseño](#principios-de-diseño)
- [Hoja de ruta](#hoja-de-ruta)
- [Documentación](#documentación)
- [Convenciones de contribución](#convenciones-de-contribución)

## Estado actual

Desarrollo inicial. La infraestructura base y la recolección de datos están operativas; todavía no existe un MVP para usuarios finales.

- Recolector reproducible de fuentes públicas con procedencia y manifiesto de ejecución.
- Datos oficiales descargados del catálogo DIGM de la Municipalidad de Guatemala:

  | Conjunto                   | Registros | Contenido                                      |
  | -------------------------- | --------: | ---------------------------------------------- |
  | Estaciones Transmetro 2025 |       169 | punto, nombre, dirección, zona, código de ruta |
  | Paradas TuBus 2025         |       278 | punto, nombre, dirección, zona, código de ruta |
  | Rutas Transmetro 2025      |        12 | geometría y código de línea/variante           |
  | Rutas TuBus 2025           |         8 | geometría y código de ruta                     |

- Esquema canónico PostgreSQL/PostGIS y entorno local con Docker Compose.
- Spike de ruteo de la ruta 801 de TuBus concluido: red reconstruida, grafo dirigido y consultas origen–destino experimentales ([informe](docs/research/spike-ruta-801.md)).

Estas fuentes son una base cartográfica; todavía no bastan para calcular un viaje completo. Faltan secuencias confiables por sentido, calendarios, frecuencias, tarifas estructuradas, transbordos y telemetría.

## Arquitectura

El sistema es modular y separa adquisición, procesamiento, almacenamiento, cálculo de rutas y presentación.

```text
Fuentes (municipalidades, ArcGIS, PDF, OSM, operadores)
        │
        ▼
Pipeline de datos (Python)
  collectors → normalizers → validators → exporters
        │
        ▼
PostgreSQL + PostGIS  ── modelo canónico con procedencia
        │
        ▼
GTFS + OpenTripPlanner ── red, itinerarios y ranking RutaGT
        │
        ▼
API RutaGT
        │
        ▼
PWA RutaGT ── mapa, búsqueda y resultados
```

Los datos atraviesan capas que nunca sobrescriben a la anterior:

```text
data/raw → data/staging → data/normalized → data/gtfs → data/published
```

## Tecnologías

| Tecnología              | Uso                                              | Estado                                                                                 |
| ----------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Python 3.12             | Recolección, validación y procesamiento de datos | En uso                                                                                 |
| uv                      | Entorno, dependencias y versión de Python        | En uso                                                                                 |
| Ruff / mypy             | Linting, formateo y tipado estático              | En uso                                                                                 |
| GeoJSON / JSON          | Datos geográficos, catálogo de fuentes           | En uso                                                                                 |
| PostgreSQL 17           | Base de datos relacional                         | Operativo (Docker)                                                                     |
| PostGIS 3.5             | Almacenamiento y operaciones geoespaciales       | Operativo (Docker)                                                                     |
| Docker Compose          | Entorno local reproducible                       | En uso                                                                                 |
| GTFS Schedule           | Formato de intercambio de datos de transporte    | Planificado                                                                            |
| OpenStreetMap           | Red vial y conexiones peatonales                 | Planificado                                                                            |
| OpenTripPlanner         | Motor de planificación multimodal                | Planificado                                                                            |
| FastAPI                 | API de datos e itinerarios (OpenAPI)             | Decidido ([ADR-0022](docs/architecture/adr/0022-fastapi-para-la-api.md))               |
| React + Vite + MapLibre | PWA ligera con mapas vectoriales abiertos        | Decidido ([ADR-0023](docs/architecture/adr/0023-react-vite-y-maplibre-para-la-pwa.md)) |

## Estructura del repositorio

```text
config/sources.json            Catálogo versionado de fuentes y rutas de salida
src/rutagt/                    Paquete Python de RutaGT
  core/                        Errores, E/S, configuración y logging compartidos
  pipeline/collectors/         Collectors registrados por tipo de fuente (ArcGIS, HTML)
  pipeline/validators/         Validaciones de calidad
  pipeline/normalizers/        Normalización de datos (Sprint 6)
  pipeline/exporters/          Exportación de datos derivados, incluido GTFS (Sprint 8)
  pipeline/cli.py              Comando rutagt-collect
database/schema/canonical.sql  Esquema canónico PostgreSQL + PostGIS
data/                          Capas de datos (raw está excluida de Git)
prototype/routing/             Spike experimental, aislado del paquete
tests/                         Pruebas (misma estructura que src/rutagt/)
docs/                          Producto, arquitectura, datos e investigación
compose.yaml                   Servicio PostgreSQL/PostGIS local
```

## Requisitos

- [uv](https://docs.astral.sh/uv/), que instala Python 3.12 y las dependencias del proyecto.
- Docker y Docker Compose para la base de datos.
- Conexión a Internet para recolectar fuentes.

## Configuración local

Instalar el entorno de desarrollo y los hooks de Git:

```powershell
uv sync
uv run pre-commit install
```

El detalle del entorno y de las herramientas de calidad está en [`CONTRIBUTING.md`](CONTRIBUTING.md#entorno-de-desarrollo).

### Variables de entorno

RutaGT utiliza variables de entorno para la configuración que varía entre equipos o contiene información sensible. Crear el archivo local a partir de la plantilla:

```powershell
Copy-Item .env.example .env
```

`.env` es exclusivamente local y no se versiona. Los secretos reales nunca deben agregarse a `.env.example`, documentación, código fuente ni commits.

| Variable             | Propósito                           | Valor por defecto         |
| -------------------- | ----------------------------------- | ------------------------- |
| `RUTAGT_ENV`         | Entorno de ejecución                | `development`             |
| `RUTAGT_DATA_DIR`    | Directorio de datos crudos          | `<project_root>/data/raw` |
| `RUTAGT_DB_HOST`     | Host de PostgreSQL                  | `localhost`               |
| `RUTAGT_DB_PORT`     | Puerto de PostgreSQL                | `5432`                    |
| `RUTAGT_DB_NAME`     | Base de datos                       | `rutagt`                  |
| `RUTAGT_DB_USER`     | Usuario de desarrollo               | `rutagt`                  |
| `RUTAGT_DB_PASSWORD` | Contraseña local                    | sin valor                 |
| `RUTAGT_LOG_LEVEL`   | Nivel de logging                    | `INFO`                    |
| `RUTAGT_LOG_FORMAT`  | Formato de logging: `text` o `json` | `text`                    |

> Nota: el recolector lee variables del entorno del proceso; el archivo `.env` no se carga automáticamente desde Python en esta etapa. `.env` sí es utilizado por Docker Compose y lo será por los servicios que se incorporen posteriormente.

### Base de datos

```powershell
docker compose up -d
docker compose ps        # el servicio db debe estar "healthy"
```

## Uso

Ejecutar desde la raíz del proyecto.

```powershell
# Listar las fuentes configuradas
uv run rutagt-collect list

# Descargar todas las fuentes
uv run rutagt-collect fetch --all

# Descargar una sola fuente
uv run rutagt-collect fetch --source muniguate_transmetro_stops_2025
```

La configuración se resuelve por defecto desde `config/sources.json` y la salida desde `data/raw/`, incluso si el comando se ejecuta desde otra carpeta. La carpeta de datos puede cambiarse con `--output` o con `RUTAGT_DATA_DIR`, el nivel de detalle de los mensajes con `RUTAGT_LOG_LEVEL` y su formato con `RUTAGT_LOG_FORMAT`. Códigos de salida: `0` éxito, `1` alguna fuente falló, `2` error de configuración.

Cada descarga genera:

- El archivo original como GeoJSON o JSON, según la fuente.
- Un archivo `.provenance.json` con URL final, fecha UTC, checksum SHA-256, conteos, licencia declarada y advertencias de validación.
- `data/raw/run_manifest.json`, con el identificador de la ejecución (`run_id`), su duración, un resumen y las fuentes exitosas y fallidas.

Una ejecución parcial no borra descargas anteriores. Si una fuente falla, el manifiesto registra el error y el proceso continúa con las demás.

<details>
<summary>Rutas de salida configuradas (relativas a <code>--output</code>)</summary>

```text
muniguate/transmetro_stops_2025.geojson
muniguate/tubus_stops_2025.geojson
muniguate/transmetro_routes_2025.geojson
muniguate/tubus_routes_2025.geojson
muniguate/transmetro_catalog_links.json
muniguate/tubus_route_105_links.json
muniguate/tubus_route_801_links.json
dgt/open_data_catalog_links.json
insivumeh/weather_catalog_links.json
```

</details>

## Pruebas

```powershell
uv run pytest          # suite por defecto, sin red ni servicios
uv run pytest --cov    # con cobertura (mínimo 90 %)
```

Niveles, marcadores y criterios en [`docs/architecture/testing-strategy.md`](docs/architecture/testing-strategy.md).

## Principios de diseño

- **Procedencia verificable.** Cada dato conserva origen, versión, licencia y vigencia. Las inferencias nunca se presentan como información oficial.
- **Datos reproducibles.** La recolección y normalización pueden repetirse para detectar cambios.
- **Separación de responsabilidades.** Collectors obtienen, normalizers transforman, validators comprueban y exporters publican.
- **Estándares abiertos.** GTFS Schedule es el formato de intercambio; GTFS-Realtime queda para una fase posterior.
- **Recomendaciones honestas.** Los tiempos estimados se presentan como rangos, nunca como horas exactas ficticias; la confianza de cada dato se usa internamente para ordenar alternativas.
- **Unidad de ruteo completa.** La unidad no es solo la línea: es `ruta + variante + sentido + calendario`.
- **Diseño accesible.** La aplicación funciona en Android e iPhone, tomando como referencia los teléfonos de gama baja.
- **Escalabilidad territorial.** Nuevos operadores y municipios se incorporan sin rediseñar la plataforma.
- **Uso legítimo de datos.** No se extraen aplicaciones privadas por ingeniería inversa ni se publican datos sin permiso.

## Hoja de ruta

El alcance, los criterios de éxito y los hitos del MVP están definidos en [`docs/product/alcance-mvp.md`](docs/product/alcance-mvp.md). El trabajo se organiza en sprints semanales ([ADR-0012](docs/architecture/adr/0012-gestion-con-scrum-semanal-en-jira.md)).

| Sprint                                | Objetivo                                                                 | Hito |
| ------------------------------------- | ------------------------------------------------------------------------ | ---- |
| 0 — Bases                             | Investigación, decisiones iniciales y recolector                         | H1   |
| 1 — Fundación reproducible            | Estructura, configuración y PostgreSQL/PostGIS con Docker                | H1   |
| 2 — Ingeniería base                   | Flujo Git, ADR, calidad automatizada, pruebas y CI                       | H1   |
| 3 — Arquitectura declarada            | Alcance, vista de arquitectura, patrones del pipeline y stack de API/PWA | H2   |
| 4 — Spike ruta 801                    | Itinerario experimental e informe de datos faltantes                     | H2   |
| 5 — Base de datos y gobierno de datos | Esquema migrado, snapshot de fuentes, calidad y versionado               | H2   |
| 6 — Normalización base                | Paradas, rutas y shapes normalizados y cargados en PostGIS               | H3   |
| 7 — Operación y secuencias            | Sentidos, variantes, horarios, frecuencias, tarifas y transbordos        | H3   |
| 8 — Primer GTFS                       | Feed GTFS válido de Transmetro y TuBus                                   | H3   |
| 9 — Routing local                     | OpenTripPlanner, ranking RutaGT y nivel de confianza                     | H4   |
| 10 — API MVP                          | Contrato OpenAPI y servicios de planificación                            | H4   |
| 11 — PWA MVP                          | Aplicación web ligera con búsqueda, alternativas y mapa                  | H5   |
| 12 — Corredor piloto                  | Metrocentro ↔ UVG validado en campo y con usuarios                       | H5   |

**Hito siguiente (H2):** arquitectura declarada, spike de la ruta 801 concluido y esquema canónico migrado con políticas de calidad de datos.

## Documentación

- [`docs/product/alcance-mvp.md`](docs/product/alcance-mvp.md): alcance, criterios de éxito e hitos del MVP.
- [`docs/architecture/overview.md`](docs/architecture/overview.md): vista de arquitectura (modelo C4).
- [`docs/architecture/adr/`](docs/architecture/adr/README.md): registro de decisiones de arquitectura (ADR).
- [`docs/architecture/pipeline-design.md`](docs/architecture/pipeline-design.md): estructura de paquetes y patrones del pipeline.
- [`docs/architecture/testing-strategy.md`](docs/architecture/testing-strategy.md): estrategia de pruebas.
- [`docs/architecture/observability.md`](docs/architecture/observability.md): registros, métricas, trazas y objetivos de servicio.
- [`docs/architecture/security.md`](docs/architecture/security.md): línea base de seguridad; reporte de vulnerabilidades en [`SECURITY.md`](SECURITY.md).
- [`docs/research/spike-ruta-801.md`](docs/research/spike-ruta-801.md): informe del spike de ruteo de la ruta 801 (hallazgos y datos faltantes).
- [`docs/architecture/canonical-schema-review.md`](docs/architecture/canonical-schema-review.md): revisión del esquema canónico y decisiones para la migración inicial.
- [`docs/data/plan-producto-y-datos.md`](docs/data/plan-producto-y-datos.md): alcance, datos requeridos, fuentes, módulos, arquitectura y fases.

## Convenciones de contribución

El flujo de trabajo completo está en [`CONTRIBUTING.md`](CONTRIBUTING.md). En resumen:

- Todo cambio parte de un ticket de Jira (`RGT-<n>`) y se desarrolla en una rama `<tipo>/RGT-<n>-<descripcion>`.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) y la clave del ticket como alcance: `feat(RGT-28): ...`.
- `main` está protegida y solo recibe cambios mediante pull request con las verificaciones en verde.
