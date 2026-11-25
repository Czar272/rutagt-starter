# ADR-0025: Formatear con Prettier los archivos que no son Python y compartir la configuración del editor

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-134    |
| Reemplaza a | —          |

## Contexto

[ADR-0019](0019-herramientas-de-entorno-y-calidad-de-codigo.md) definió Ruff como formateador de Python, pero no estableció un formateador para el resto de archivos (Markdown, YAML, JSON, HTML y, a futuro, TypeScript de la PWA). El editor del equipo formatea esos archivos con Prettier al guardar, mientras que pre-commit y el CI no lo hacían. El resultado fueron diffs con cambios masivos de alineación en tablas Markdown, mezclados con cambios de contenido, y conflictos difíciles de resolver al integrar ramas.

## Decisión

- **Prettier** formatea todos los archivos de texto que soporta, excepto Python, que sigue formateándose con Ruff.
- La configuración es explícita en `.prettierrc.json` (valores por defecto de Prettier 3 con `endOfLine: lf`) y las exclusiones en `.prettierignore` (datos, cachés, lockfiles y Python).
- Prettier se ejecuta en **pre-commit** con una versión fijada y, por lo tanto, también en el trabajo de calidad del CI ([ADR-0021](0021-integracion-continua-con-github-actions.md)).
- El repositorio versiona la configuración de VS Code en `.vscode/`: formato al guardar con Ruff para Python y Prettier para el resto, extensiones recomendadas y la extensión Black marcada como no deseada.
- Los cambios exclusivamente de formato se registran con el tipo de commit `style`.

## Alternativas consideradas

| Alternativa                                     | Ventajas                                | Desventajas                                                  | Motivo de descarte                                           |
| ----------------------------------------------- | --------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Sin formateador para archivos que no son Python | Ninguna configuración                   | Cada editor formatea distinto; diffs y conflictos de formato | Comprobado como problemático                                 |
| Biome                                           | Más rápido, linter y formateador en uno | No formatea Markdown ni YAML                                 | Cobertura de formatos insuficiente                           |
| dprint                                          | Rápido y configurable                   | Menos extendido; menor integración con editores              | Prettier ya es el formateador del editor del equipo          |
| Black para Python en el editor                  | Ya instalado                            | Puede diferir de Ruff en casos límite                        | El editor debe usar la misma herramienta que pre-commit y CI |

## Consecuencias

### Positivas

- El formato es idéntico en el editor, en pre-commit y en el CI.
- Los pull requests muestran solo cambios de contenido.
- La PWA hereda la configuración de formato desde su inicio.

### Negativas y riesgos

- pre-commit instala un entorno de Node para ejecutar Prettier, lo que agrega tiempo a la primera ejecución.
- La versión de Prettier debe actualizarse explícitamente en `.pre-commit-config.yaml`.

## Verificación

- `.prettierrc.json`, `.prettierignore`, `.vscode/settings.json` y `.vscode/extensions.json` existen en el repositorio.
- `uv run pre-commit run --all-files` termina sin modificar archivos.
- El trabajo «Calidad de código» del CI ejecuta el hook de Prettier.

## Referencias

- [Prettier](https://prettier.io/), [Rationale](https://prettier.io/docs/rationale).
- `CONTRIBUTING.md`, sección «Calidad de código».
