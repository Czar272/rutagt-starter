# ADR-0020: Usar pytest con cobertura mínima y pruebas sin red por defecto

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-124    |
| Reemplaza a | —          |

## Contexto

Las primeras pruebas del recolector usaban `unittest` y cubrían el 41 % del código: las funciones que consultan servicios externos (ArcGIS, páginas HTML) y la interfaz de línea de comandos no tenían pruebas. El proyecto incorporará base de datos, exportación GTFS, motor de ruteo y API, por lo que necesita una estrategia que distinga pruebas rápidas y deterministas de las que requieren servicios o Internet, y un criterio objetivo de cobertura.

## Decisión

- Usamos **pytest** como framework de pruebas y **pytest-cov** para medir cobertura de líneas y ramas sobre `pipeline/`.
- La cobertura mínima es **90 %**; la ejecución con `--cov` falla por debajo del umbral.
- Las pruebas se clasifican con marcadores: sin marcador (unitarias y de datos), `integration` (servicios locales) y `network` (fuentes reales). La suite por defecto excluye `integration` y `network`.
- Las pruebas no acceden a Internet ni a `data/raw/`: la red se simula con `monkeypatch` y los datos de muestra se versionan en `tests/fixtures/`.
- Se activan `--strict-markers`, `--strict-config` y `xfail_strict`.

El detalle está en [`docs/architecture/testing-strategy.md`](../testing-strategy.md).

## Alternativas consideradas

| Alternativa                    | Ventajas             | Desventajas                                                  | Motivo de descarte                                                     |
| ------------------------------ | -------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------- |
| Mantener `unittest`            | Biblioteca estándar  | Más verboso; sin fixtures ni parametrización expresivas      | pytest es el estándar de facto y ejecuta pruebas `unittest` existentes |
| Grabar respuestas reales (VCR) | Respuestas realistas | Grabaciones grandes y con posibles restricciones de licencia | Se prefieren respuestas mínimas construidas para cada caso             |
| Sin umbral de cobertura        | Menos fricción       | La cobertura se degrada sin que se note                      | Se requiere un criterio objetivo y verificable                         |

## Consecuencias

### Positivas

- La suite es rápida, determinista y ejecutable sin conexión.
- La cobertura del recolector pasó de 41 % a más de 97 %.
- La cobertura y los resultados son evidencia verificable en cada pull request.

### Negativas y riesgos

- Las simulaciones pueden divergir del comportamiento real de las fuentes; se mitiga con pruebas `network` programadas.
- El umbral exige escribir pruebas junto con cada cambio de código.

## Verificación

- `pyproject.toml` contiene `[tool.pytest.ini_options]` con marcadores y `[tool.coverage.report] fail_under = 90`.
- `uv run pytest --cov` termina sin errores y reporta una cobertura de al menos 90 %.

## Referencias

- [pytest](https://docs.pytest.org/), [coverage.py](https://coverage.readthedocs.io/).
- [`docs/architecture/testing-strategy.md`](../testing-strategy.md).
