# Estrategia de pruebas

Este documento define qué se prueba en RutaGT, con qué herramientas, dónde viven las pruebas y qué umbrales debe cumplir cada cambio. La decisión está registrada en [ADR-0020](adr/0020-pytest-y-cobertura-como-estrategia-de-pruebas.md).

## Objetivos

1. Detectar regresiones antes de integrar cualquier cambio a `main`.
2. Garantizar que el pipeline conserva la procedencia y la calidad de los datos ([ADR-0004](adr/0004-capas-de-datos-inmutables-con-procedencia.md)).
3. Ejecutar la suite completa de forma rápida, determinista y sin depender de Internet.
4. Producir evidencia verificable (resultados y cobertura) en cada pull request.

## Niveles de prueba

| Nivel             | Qué valida                                                                                                                                             | Dependencias                            | Marcador      | Ejecución                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- | ------------- | -------------------------------------------------- |
| Unitarias         | Funciones y clases aisladas: parsers, validaciones, transformaciones, CLI                                                                              | Ninguna; red y servicios simulados      | —             | Siempre, local y CI                                |
| De datos          | Contratos de archivos versionados: `config/sources.json`, fixtures, salidas GTFS                                                                       | Ninguna                                 | —             | Siempre, local y CI                                |
| Integración       | Interacción con PostgreSQL/PostGIS, migraciones, carga de datos y OpenTripPlanner                                                                      | Servicios de Docker Compose             | `integration` | Bajo demanda local; CI con servicios               |
| Red               | Disponibilidad y estructura de fuentes oficiales reales                                                                                                | Internet                                | `network`     | Bajo demanda y programadas; nunca bloquean un PR   |
| Extremo a extremo | Interfaces en un navegador real (Playwright + Chromium): hoy el mapa del spike; desde el Sprint 9, itinerarios de la API y la PWA contra rutas doradas | Navegador; servicios externos simulados | `e2e`         | Local bajo demanda; CI en el trabajo «Pruebas e2e» |

Por defecto, `pytest` excluye las pruebas `integration`, `network` y `e2e` (`-m "not integration and not network and not e2e"` en `pyproject.toml`).

## Herramientas

| Herramienta              | Uso                                                                               |
| ------------------------ | --------------------------------------------------------------------------------- |
| pytest                   | Ejecución de pruebas, fixtures, parametrización y marcadores                      |
| pytest-cov (coverage.py) | Cobertura de líneas y ramas sobre el paquete `rutagt`                             |
| `monkeypatch` de pytest  | Simulación de red (`http_get`, `get_json`, `urlopen`) y de esperas (`time.sleep`) |
| `tmp_path` de pytest     | Archivos temporales aislados por prueba                                           |

## Organización

```text
tests/
├── conftest.py                 # fixtures globales (cuando existan)
├── fixtures/                   # datos de muestra pequeños y versionados
│   └── html/
└── <módulo>/                   # refleja la estructura de src/rutagt/
    ├── conftest.py             # fixtures del componente
    └── test_<aspecto>.py
```

- Las pruebas reflejan la estructura del código: `src/rutagt/pipeline/collectors/` → `tests/pipeline/collectors/`, e importan los módulos directamente (`from rutagt.pipeline.collectors import arcgis`).
- Un archivo por aspecto del componente (`test_http.py`, `test_arcgis.py`, `test_cli.py`).
- Nombres descriptivos en inglés que expresan el comportamiento: `test_http_get_retries_transient_errors_with_backoff`.
- Estructura _Arrange-Act-Assert_, separada por líneas en blanco.

## Datos de prueba

- Las pruebas **nunca** leen `data/raw/` ni otras capas de datos reales: su contenido cambia y no está versionado.
- Los datos de muestra viven en `tests/fixtures/`, son pequeños, anonimizados y representan casos concretos (codificación, geometrías, paginación).
- Las respuestas de servicios externos se simulan en la propia prueba o como archivos en `tests/fixtures/`.
- Toda escritura se hace en `tmp_path`.

## Umbrales y criterios

| Criterio                                               | Valor                                                                     |
| ------------------------------------------------------ | ------------------------------------------------------------------------- |
| Cobertura mínima del paquete `rutagt` (líneas y ramas) | **90 %**; la ejecución falla por debajo                                   |
| Pruebas que fallan en `main`                           | 0                                                                         |
| Pruebas dependientes de red en la suite por defecto    | 0                                                                         |
| Pruebas omitidas sin motivo                            | No permitidas: todo `skip` o `xfail` indica la razón; `xfail` es estricto |

El umbral se revisará al alza a medida que crezca el código. Un pull request no puede reducir la cobertura por debajo del umbral.

## Comandos

```powershell
uv run pytest                                  # suite por defecto
uv run pytest --cov                            # con cobertura y umbral
uv run pytest tests/pipeline/collectors/test_http.py   # un archivo
uv run pytest -k retries                       # por nombre
uv run pytest -m integration                   # pruebas de integración
uv run pytest -m network                       # pruebas contra fuentes reales
uv run playwright install chromium             # una vez, para las pruebas e2e
uv run pytest prototype/routing -m e2e         # pruebas e2e del mapa del spike
```

## Integración continua

La suite por defecto con cobertura se ejecutará en cada push y pull request (RGT-107). Las pruebas de integración se ejecutarán en CI con un servicio PostgreSQL/PostGIS cuando existan migraciones (RGT-29). Las pruebas de red se ejecutarán de forma programada para detectar cambios en las fuentes oficiales sin bloquear el desarrollo.
