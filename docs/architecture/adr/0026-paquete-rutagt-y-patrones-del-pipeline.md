# ADR-0026: Organizar el código en el paquete `rutagt` con collectors registrados por tipo de fuente

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-122    |
| Reemplaza a | —          |

## Contexto

El recolector inicial era un único script (`pipeline/collectors/collect.py`) que mezclaba cliente HTTP, collectors de ArcGIS y HTML, validaciones, utilidades de E/S y la línea de comandos. No era un paquete importable: las pruebas lo cargaban por ruta con `importlib`. Agregar un tipo de fuente obligaba a modificar un despachador `if/elif`, y no existía una convención para los normalizers, validators y exporters que se construirán en los próximos sprints ni para la API ([ADR-0022](0022-fastapi-para-la-api.md)), que vivirá en el mismo monolito modular ([ADR-0015](0015-monolito-modular-para-el-mvp.md)).

## Decisión

- Todo el código Python de producción vive en el paquete instalable **`rutagt`** con estructura **`src/`** (`src/rutagt/`), construido con `uv_build` y declarado en `pyproject.toml`.
- **`rutagt.core`** contiene lo transversal (errores, E/S determinista, configuración `RUTAGT_*`, logging) y no depende de otros módulos de `rutagt`.
- **`rutagt.pipeline`** se organiza por etapas: `collectors`, `validators`, `normalizers` y `exporters`. Las etapas se comunican mediante archivos de `data/` y su procedencia, no importándose entre sí.
- Los **collectors** son funciones registradas por tipo de fuente con `@register_collector("<tipo>")` (patrones _Strategy_ y _Registry_); `collect_source` despacha según el campo `type` del catálogo.
- Los **validators** son funciones puras sin efectos secundarios.
- Las excepciones heredan de `RutaGTError` (`ConfigurationError`, `SourceError`); solo la línea de comandos las traduce a códigos de salida.
- El recolector se ejecuta con el comando **`rutagt-collect`**.
- Las pruebas reflejan la estructura de `src/rutagt/` e importan los módulos directamente.

El detalle está en [`docs/architecture/pipeline-design.md`](../pipeline-design.md). Esta decisión reemplaza la ubicación `pipeline/collectors/collect.py` mencionada en ADR anteriores; esas menciones se conservan como registro histórico.

## Alternativas consideradas

| Alternativa                            | Ventajas                   | Desventajas                                                                           | Motivo de descarte                                      |
| -------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Mantener scripts sueltos               | Sin cambios                | No importable, despachador rígido, pruebas acopladas a rutas                          | No escala a nuevas etapas ni a la API                   |
| Paquete plano en la raíz (`rutagt/`)   | Sin carpeta `src/`         | Las pruebas pueden importar el código sin instalarlo y ocultar errores de empaquetado | La estructura `src/` garantiza probar lo instalado      |
| Paquetes separados para pipeline y API | Despliegues independientes | Versionado y dependencias duplicados para un equipo reducido                          | Contrario al monolito modular del MVP                   |
| Clases base abstractas para cada etapa | Comportamiento compartido  | Más ceremonia que funciones registradas para el caso actual                           | Las funciones registradas son suficientes y más simples |

## Consecuencias

### Positivas

- Agregar un tipo de fuente consiste en crear un módulo con una función registrada, sin modificar el despachador.
- El código es importable y reutilizable por la API y por futuras etapas.
- Errores con significado de dominio y códigos de salida consistentes.
- La cobertura medida sobre el paquete alcanza 99 %.

### Negativas y riesgos

- Los comandos cambian de `python pipeline/collectors/collect.py` a `rutagt-collect`.
- El registro de collectors es estado global; las pruebas que lo modifican deben aislarlo.

## Verificación

- `pyproject.toml` declara `[build-system]` con `uv_build` y el script `rutagt-collect`.
- `src/rutagt/` contiene `core/` y `pipeline/` con la estructura descrita; no existe `pipeline/` en la raíz.
- `uv run rutagt-collect list` lista las fuentes del catálogo.
- `tests/pipeline/collectors/test_base.py` verifica el registro de collectors.

## Referencias

- [`docs/architecture/pipeline-design.md`](../pipeline-design.md).
- [Python Packaging User Guide — src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
