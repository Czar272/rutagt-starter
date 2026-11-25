# ADR-0019: Usar uv, Ruff, mypy y pre-commit con Python 3.12

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-123    |
| Reemplaza a | —          |

## Contexto

Hasta ahora el proyecto no tenía un entorno reproducible ni herramientas que aplicaran un estilo común: cada equipo usaba la versión de Python instalada en el sistema, no había archivo de dependencias y la calidad del código dependía de revisiones manuales. [ADR-0005](0005-python-para-el-pipeline-de-datos.md) fijó Python como lenguaje del pipeline con un mínimo de 3.10, versión cuyo soporte de seguridad terminó en octubre de 2026.

Para que el proyecto sea auditable y mantenible por más personas, el entorno debe poder recrearse con exactitud y las convenciones deben verificarse automáticamente, tanto en cada equipo como en la integración continua.

## Decisión

| Aspecto | Decisión |
| --- | --- |
| Versión de Python | **3.12** como mínimo (`requires-python = ">=3.12"`), fijada en `.python-version`. Actualiza el mínimo indicado en ADR-0005. |
| Entorno y dependencias | **uv**: entorno virtual, instalación de Python y dependencias, con `uv.lock` versionado para instalaciones reproducibles. |
| Configuración | **`pyproject.toml`** como fuente única de metadatos y configuración de herramientas. |
| Linting y formateo | **Ruff** con reglas de pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, bugbear, comprehensions, simplify, pathlib, bandit (seguridad) y Ruff. |
| Tipado | **mypy** en modo estricto para `pipeline/`; las pruebas pueden omitir anotaciones. |
| Verificación local | **pre-commit** ejecuta las verificaciones en cada commit y valida Conventional Commits en el mensaje. |
| Archivos de texto | UTF-8 y finales de línea LF, aplicados por `.gitattributes` y `.editorconfig`. |

Las mismas herramientas y versiones se ejecutarán en la integración continua (RGT-107).

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| pip + venv | Incluido en Python | Sin lockfile nativo; reproducibilidad manual | Menor garantía de entornos idénticos |
| Poetry | Maduro, con lockfile | Más lento; configuración propia fuera del estándar de grupos de dependencias | uv cubre lo mismo con mejor rendimiento |
| Black + isort + Flake8 | Herramientas consolidadas | Tres herramientas y configuraciones; más lentas | Ruff las reemplaza con una sola |
| Pyright | Rápido, buen soporte en editores | Menos usado como verificador en CI de proyectos Python de datos | mypy es el estándar de referencia |
| Python 3.13 | Versión más reciente | Soporte todavía incompleto en algunas librerías geoespaciales | 3.12 ofrece mejor compatibilidad |

## Consecuencias

### Positivas

- Cualquier persona recrea el entorno exacto con `uv sync`.
- Los errores de estilo, tipos y seguridad se detectan antes del commit.
- El historial de commits mantiene un formato uniforme verificado automáticamente.

### Negativas y riesgos

- Requiere instalar uv en cada equipo.
- El modo estricto de mypy exige anotar todo el código del pipeline.
- Las versiones de las herramientas y hooks deben actualizarse periódicamente (`uv lock --upgrade`, `pre-commit autoupdate`).

## Verificación

- `pyproject.toml` declara `requires-python = ">=3.12"` y la configuración de Ruff y mypy.
- `uv.lock`, `.python-version`, `.pre-commit-config.yaml`, `.gitattributes` y `.editorconfig` existen en la raíz.
- `uv run pre-commit run --all-files` termina sin errores.

## Referencias

- [uv](https://docs.astral.sh/uv/), [Ruff](https://docs.astral.sh/ruff/), [mypy](https://mypy.readthedocs.io/), [pre-commit](https://pre-commit.com/).
- [Estado de las versiones de Python](https://devguide.python.org/versions/).
- `CONTRIBUTING.md`, secciones «Entorno de desarrollo» y «Calidad de código».
