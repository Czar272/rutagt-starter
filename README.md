# RutaGT

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

  | Conjunto                   | Registros | Contenido                                       |
  | -------------------------- | --------: | ----------------------------------------------- |
  | Estaciones Transmetro 2025 |       169 | punto, nombre, dirección, zona, código de ruta  |
  | Paradas TuBus 2025         |       278 | punto, nombre, dirección, zona, código de ruta  |
  | Rutas Transmetro 2025      |        12 | geometría y código de línea/variante            |
  | Rutas TuBus 2025           |         8 | geometría y código de ruta                      |

- Esquema canónico PostgreSQL/PostGIS y entorno local con Docker Compose.
- Spike de ruteo en curso sobre la ruta 801 de TuBus (`prototype/routing/`).

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

| Tecnología            | Uso                                               | Estado             |
| --------------------- | ------------------------------------------------- | ------------------ |
| Python 3.12           | Recolección, validación y procesamiento de datos  | En uso             |
| uv                    | Entorno, dependencias y versión de Python         | En uso             |
| Ruff / mypy           | Linting, formateo y tipado estático               | En uso             |
| GeoJSON / JSON        | Datos geográficos, catálogo de fuentes            | En uso             |
| PostgreSQL 17         | Base de datos relacional                          | Operativo (Docker) |
| PostGIS 3.5           | Almacenamiento y operaciones geoespaciales        | Operativo (Docker) |
| Docker Compose        | Entorno local reproducible                        | En uso             |
| GTFS Schedule         | Formato de intercambio de datos de transporte     | Planificado        |
| OpenStreetMap         | Red vial y conexiones peatonales                  | Planificado        |
| OpenTripPlanner       | Motor de planificación multimodal                 | Planificado        |
| API                   | Exposición de datos e itinerarios                 | Por definir        |
| PWA                   | Aplicación web instalable y ligera                | Por definir        |

## Estructura del repositorio

```text
config/sources.json            Catálogo versionado de fuentes y rutas de salida
pipeline/
  collectors/collect.py        Recolector de servicios ArcGIS y enlaces HTML
  normalizers/                 Transformaciones sin modificar los datos originales
  validators/                  Validaciones de calidad
  exporters/                   Exportación de datos derivados, incluido GTFS
database/schema/canonical.sql  Esquema canónico PostgreSQL + PostGIS
data/                          Capas de datos (raw está excluida de Git)
prototype/routing/             Spike experimental, aislado del pipeline
tests/                         Pruebas unitarias
docs/                          Plan de producto, datos y solicitudes institucionales
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

| Variable             | Propósito                  | Valor por defecto         |
| -------------------- | -------------------------- | ------------------------- |
| `RUTAGT_ENV`         | Entorno de ejecución       | `development`             |
| `RUTAGT_DATA_DIR`    | Directorio de datos crudos | `<project_root>/data/raw` |
| `RUTAGT_DB_HOST`     | Host de PostgreSQL         | `localhost`               |
| `RUTAGT_DB_PORT`     | Puerto de PostgreSQL       | `5432`                    |
| `RUTAGT_DB_NAME`     | Base de datos              | `rutagt`                  |
| `RUTAGT_DB_USER`     | Usuario de desarrollo      | `rutagt`                  |
| `RUTAGT_DB_PASSWORD` | Contraseña local           | sin valor                 |
| `RUTAGT_LOG_LEVEL`   | Nivel de logging           | `INFO`                    |

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
uv run python pipeline/collectors/collect.py list

# Descargar todas las fuentes
uv run python pipeline/collectors/collect.py fetch --all --output data/raw

# Descargar una sola fuente
uv run python pipeline/collectors/collect.py fetch `
  --source muniguate_transmetro_stops_2025 `
  --output data/raw
```

La configuración se resuelve por defecto desde `config/sources.json` y la salida desde `data/raw/`, incluso si el comando se ejecuta desde otra carpeta. La carpeta de datos puede cambiarse con `RUTAGT_DATA_DIR`.

Cada descarga genera:

- El archivo original como GeoJSON o JSON, según la fuente.
- Un archivo `.provenance.json` con URL final, fecha UTC, checksum SHA-256, conteos, licencia declarada y advertencias de validación.
- `data/raw/run_manifest.json`, con las fuentes exitosas y fallidas de la ejecución.

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
- **Confianza explícita.** Horarios, tiempos o conexiones estimados se distinguen de los confirmados.
- **Unidad de ruteo completa.** La unidad no es solo la línea: es `ruta + variante + sentido + calendario`.
- **Diseño accesible.** La aplicación debe funcionar en teléfonos de gama baja.
- **Escalabilidad territorial.** Nuevos operadores y municipios se incorporan sin rediseñar la plataforma.
- **Uso legítimo de datos.** No se extraen aplicaciones privadas por ingeniería inversa ni se publican datos sin permiso.

## Hoja de ruta

| Etapa                             | Objetivo                                      |
| --------------------------------- | --------------------------------------------- |
| Sprint 0 — Bases                  | Investigación, decisiones y estructura        |
| Sprint 1 — Fundación reproducible | Docker, base de datos, esquema y herramientas |
| Sprint 2 — Normalización base     | Transformación y validación de datos          |
| Sprint 3 — Operación y secuencias | Sentidos, paradas, horarios y frecuencias     |
| Sprint 4 — Primer GTFS            | Feed GTFS válido de Transmetro y TuBus        |
| Sprint 5 — Routing local          | OpenTripPlanner, itinerarios, ranking         |
| Sprint 6 — API MVP                | Servicios de consulta de datos e itinerarios  |
| Sprint 7 — PWA MVP                | Aplicación web/móvil inicial                  |
| Sprint 8 — Corredor piloto        | Validación con recorridos reales              |

**Hito siguiente:** un piloto estático validado para Transmetro y TuBus capaz de devolver opciones reproducibles entre dos puntos, donde cada instrucción muestre recorrido, sentido, parada de ascenso y descenso, caminata, tarifa y nivel de confianza.

## Documentación

- [`docs/architecture/adr/`](docs/architecture/adr/README.md): registro de decisiones de arquitectura (ADR).
- [`docs/architecture/testing-strategy.md`](docs/architecture/testing-strategy.md): estrategia de pruebas.
- [`docs/data/plan-producto-y-datos.md`](docs/data/plan-producto-y-datos.md): alcance, datos requeridos, fuentes, módulos, arquitectura y fases.
- [`docs/institutions/solicitudes-informacion.md`](docs/institutions/solicitudes-informacion.md): plantillas de solicitudes a municipalidades, DGT y operadores.

## Convenciones de contribución

El flujo de trabajo completo está en [`CONTRIBUTING.md`](CONTRIBUTING.md). En resumen:

- Todo cambio parte de un ticket de Jira (`RGT-<n>`) y se desarrolla en una rama `<tipo>/RGT-<n>-<descripcion>`.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) y la clave del ticket como alcance: `feat(RGT-28): ...`.
- `main` está protegida y solo recibe cambios mediante pull request con las verificaciones en verde.
