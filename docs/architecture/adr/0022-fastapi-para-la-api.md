# ADR-0022: Construir la API de RutaGT con FastAPI

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-120    |
| Reemplaza a | —          |

## Contexto

La API de RutaGT expone paradas cercanas, rutas, búsqueda de lugares y planificación de itinerarios (épica RGT-5). Combina consultas espaciales sobre PostGIS ([ADR-0002](0002-postgresql-postgis-como-modelo-canonico.md)) con llamadas a OpenTripPlanner ([ADR-0014](0014-opentripplanner-como-motor-de-planificacion.md)) y aplica el ranking y el nivel de confianza propios ([ADR-0017](0017-confianza-explicita-en-itinerarios.md)). Se desplegará como monolito modular ([ADR-0015](0015-monolito-modular-para-el-mvp.md)).

Requisitos:

- Contrato **OpenAPI** como fuente de verdad para la PWA y para terceros (RGT-63).
- Integración nativa con **PostGIS** y tipos geoespaciales.
- Rendimiento suficiente para p95 < 3 s en planificación (criterio C6 del [alcance del MVP](../../product/alcance-mvp.md)), donde el costo dominante es OpenTripPlanner y la base de datos, no el framework.
- Mantenible por un equipo reducido, reutilizando las herramientas ya adoptadas ([ADR-0019](0019-herramientas-de-entorno-y-calidad-de-codigo.md), [ADR-0020](0020-pytest-y-cobertura-como-estrategia-de-pruebas.md), [ADR-0021](0021-integracion-continua-con-github-actions.md)).

## Evaluación

Escala de 1 (deficiente) a 5 (excelente).

| Criterio                                                    |  Peso | FastAPI (Python) | Django REST + GeoDjango | NestJS (TypeScript) | Go (chi + sqlc) |
| ----------------------------------------------------------- | ----: | :--------------: | :---------------------: | :-----------------: | :-------------: |
| Integración geoespacial (PostGIS, geometrías, proyecciones) |  20 % |        5         |            5            |          3          |        3        |
| Coherencia con el stack y herramientas existentes           |  20 % |        5         |            4            |          2          |        2        |
| Contrato OpenAPI y validación de datos                      |  15 % |        5         |            3            |          4          |        3        |
| Rendimiento y concurrencia (E/S hacia OTP y PostGIS)        |  15 % |        4         |            3            |          4          |        5        |
| Tipado estático y calidad verificable                       |  10 % |        4         |            3            |          5          |        4        |
| Ecosistema, documentación y disponibilidad de talento       |  10 % |        4         |            4            |          5          |        3        |
| Simplicidad de despliegue y operación                       |  10 % |        4         |            4            |          4          |        5        |
| **Puntaje ponderado**                                       | 100 % |     **4.55**     |          3.80           |        3.60         |      3.40       |

Observaciones:

- **FastAPI** genera OpenAPI desde los modelos Pydantic, es asíncrono (adecuado para esperar a OTP y a la base) y comparte lenguaje, gestor de entorno, linters, tipado y framework de pruebas con el pipeline.
- **Django REST + GeoDjango** tiene el mejor soporte geoespacial integrado, pero arrastra un ORM y un panel de administración que el MVP no necesita, y su generación de OpenAPI depende de extensiones.
- **NestJS** ofrece una estructura modular muy clara, pero introduce un segundo ecosistema (Node) en el backend y su soporte PostGIS es menos maduro.
- **Go** destaca en rendimiento y despliegue, pero exige más código para validación, OpenAPI y geometrías, sin beneficio perceptible dado que el cuello de botella es OTP.

## Decisión

Construimos la API con **FastAPI** sobre **Python 3.12**, con:

| Aspecto                    | Elección                                                                                                                                    |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework                  | FastAPI con servidor ASGI Uvicorn                                                                                                           |
| Modelos y validación       | Pydantic v2; el contrato OpenAPI se genera desde el código y se versiona                                                                    |
| Acceso a datos             | SQLAlchemy 2 con GeoAlchemy2 y el driver psycopg 3; consultas espaciales en SQL/PostGIS                                                     |
| Geometrías                 | GeoJSON en la API; Shapely solo donde se requiera cálculo en la aplicación                                                                  |
| Cliente de OpenTripPlanner | `httpx` asíncrono con tiempos de espera explícitos                                                                                          |
| Configuración              | Variables `RUTAGT_*` validadas con pydantic-settings ([ADR-0009](0009-configuracion-mediante-variables-de-entorno.md))                      |
| Pruebas                    | pytest con el cliente de pruebas de FastAPI; integración contra PostGIS con marcador `integration`                                          |
| Estructura                 | Módulos por dominio (paradas, rutas, lugares, planificación) dentro de un único servicio ([ADR-0015](0015-monolito-modular-para-el-mvp.md)) |

La estructura de paquetes compartida entre la API y el pipeline se define en RGT-122. La herramienta de migraciones del esquema se decide en RGT-29.

## Consecuencias

### Positivas

- Un solo lenguaje y un solo conjunto de herramientas para todo el backend: menor costo de mantenimiento y de incorporación de personas.
- Contrato OpenAPI siempre sincronizado con la implementación.
- Reutilización directa de modelos y utilidades del pipeline cuando sea necesario.

### Negativas y riesgos

- Python es menos eficiente en CPU que Go; se mitiga manteniendo el cálculo pesado en PostGIS y OpenTripPlanner y midiendo el criterio C6.
- La programación asíncrona exige cuidado para no bloquear el bucle de eventos con operaciones síncronas.

## Verificación

- El servicio de la API vive en el repositorio con dependencias en `pyproject.toml`/`uv.lock` y pasa el mismo CI.
- El contrato OpenAPI generado se versiona y se valida en CI (RGT-63, RGT-69).

## Referencias

- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/), [SQLAlchemy](https://www.sqlalchemy.org/), [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/), [HTTPX](https://www.python-httpx.org/).
