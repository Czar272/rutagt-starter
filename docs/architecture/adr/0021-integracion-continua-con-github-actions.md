# ADR-0021: Usar GitHub Actions para la integración continua

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-107    |
| Reemplaza a | —          |

## Contexto

[ADR-0011](0011-flujo-git-con-ramas-por-ticket.md) establece que `main` solo recibe cambios mediante pull request con verificaciones en verde, y [ADR-0019](0019-herramientas-de-entorno-y-calidad-de-codigo.md) y [ADR-0020](0020-pytest-y-cobertura-como-estrategia-de-pruebas.md) definen las herramientas de calidad y pruebas. Las verificaciones locales con pre-commit pueden omitirse o ejecutarse con un entorno distinto; se necesita un verificador independiente, reproducible y visible en cada cambio.

## Decisión

Usamos **GitHub Actions** con el flujo `.github/workflows/ci.yml`:

| Trabajo            | Disparador                           | Qué verifica                                                                                      |
| ------------------ | ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Calidad de código  | Push a cualquier rama y pull request | Todos los hooks de pre-commit: archivos, Ruff, formato y mypy                                     |
| Pruebas            | Push a cualquier rama y pull request | pytest con cobertura mínima de 90 % en Ubuntu y Windows con Python 3.12, y Ubuntu con Python 3.13 |
| Mensajes de commit | Pull request                         | Título del pull request y cada commit cumplen Conventional Commits                                |

Principios:

- **Mismas herramientas que en local**: el CI ejecuta `uv sync` con `uv.lock` (`UV_LOCKED=1`) y los mismos hooks de pre-commit.
- **Mínimo privilegio**: `permissions: contents: read`.
- **Acciones fijadas por SHA** de commit, con la versión en un comentario, para evitar cambios no revisados en dependencias de terceros.
- **Evidencia**: los resultados JUnit y la cobertura en XML se publican como artefactos durante 30 días.
- **Cancelación** de ejecuciones obsoletas de la misma rama o pull request.
- **Verificaciones obligatorias**: los trabajos de calidad, pruebas y mensajes de commit son requisitos del ruleset de `main`.
- **Dependabot** propone semanalmente actualizaciones de las acciones y de las dependencias de Python.

## Alternativas consideradas

| Alternativa                   | Ventajas                 | Desventajas                                          | Motivo de descarte                                             |
| ----------------------------- | ------------------------ | ---------------------------------------------------- | -------------------------------------------------------------- |
| GitLab CI / Jenkins           | Muy configurables        | Requieren migrar el repositorio u operar un servidor | El repositorio vive en GitHub                                  |
| CircleCI / Azure Pipelines    | Servicios maduros        | Integración y permisos externos adicionales          | GitHub Actions es nativo y gratuito para repositorios públicos |
| Acciones por etiqueta (`@v7`) | Actualización automática | Una etiqueta puede moverse a código no revisado      | Se prefiere fijar por SHA con Dependabot                       |

## Consecuencias

### Positivas

- Ningún cambio llega a `main` sin pasar calidad, pruebas y formato de commits.
- La matriz detecta problemas de compatibilidad entre sistemas operativos y versiones de Python.
- Cada ejecución deja evidencia descargable para auditoría.

### Negativas y riesgos

- Los pushes a ramas con pull request abierto ejecutan el flujo dos veces; se acepta para verificar también ramas sin pull request.
- Las acciones fijadas por SHA requieren revisar las propuestas de Dependabot.

## Verificación

- `.github/workflows/ci.yml` y `.github/dependabot.yml` existen en el repositorio.
- El ruleset «Protección de main» exige los trabajos del flujo CI como verificaciones de estado.
- Cada pull request muestra los trabajos del flujo CI en verde antes de integrarse.

## Referencias

- [GitHub Actions — Security hardening](https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions).
- [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv).
