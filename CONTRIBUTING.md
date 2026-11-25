# Guía de contribución

Este documento define cómo se planifica, desarrolla, revisa e integra el trabajo en RutaGT. Su objetivo es que cada cambio sea trazable desde el ticket de Jira hasta el commit que lo implementa.

## Contenido

- [Flujo de trabajo](#flujo-de-trabajo)
- [Ramas](#ramas)
- [Commits](#commits)
- [Pull requests](#pull-requests)
- [Integración a main](#integración-a-main)
- [Definition of Ready](#definition-of-ready)
- [Definition of Done](#definition-of-done)
- [Versionado y releases](#versionado-y-releases)

## Flujo de trabajo

Todo cambio parte de un ticket del proyecto **RGT** en Jira.

1. **Seleccionar el ticket** del sprint activo y revisar objetivo, alcance y criterios de aceptación.
2. **Mover el ticket a _In Progress_.**
3. **Crear una rama** desde `main` actualizada, siguiendo la convención de nombres.
4. **Implementar en commits pequeños**, limitados al alcance del ticket.
5. **Ejecutar las verificaciones locales** (pruebas y herramientas de calidad).
6. **Abrir un pull request** hacia `main` usando la plantilla.
7. **Mover el ticket a _In Review_** mientras el pull request está abierto.
8. **Integrar** cuando las verificaciones de CI estén en verde y los criterios de aceptación se cumplan.
9. **Cerrar el ticket** con un comentario breve que describa lo realizado, cómo se verificó y el enlace al pull request.

Los cambios que no corresponden a ningún ticket (correcciones menores de documentación o mantenimiento) siguen el mismo flujo con una rama `docs/` o `chore/` sin clave de ticket.

### Estados de Jira

| Estado        | Significado                                             |
| ------------- | ------------------------------------------------------- |
| `To Do`       | Planificado, sin iniciar                                |
| `In Progress` | En desarrollo en una rama                               |
| `IN REVIEW`   | Pull request abierto, pendiente de CI o revisión        |
| `BLOCKED`     | Detenido por una dependencia externa; indicar el motivo |
| `Done`        | Integrado en `main` y criterios de aceptación cumplidos |

## Ramas

`main` es la única rama de larga duración. Siempre debe estar en estado desplegable y solo recibe cambios mediante pull request.

Las ramas de trabajo se crean desde `main` y se eliminan después de integrarse.

```text
<tipo>/RGT-<n>-<descripcion-corta>
```

| Prefijo     | Uso                                                  |
| ----------- | ---------------------------------------------------- |
| `feature/`  | Funcionalidad nueva o trabajo planificado de ticket  |
| `fix/`      | Corrección de un defecto                             |
| `docs/`     | Cambios exclusivamente de documentación              |
| `chore/`    | Mantenimiento, configuración o dependencias          |
| `refactor/` | Reestructuración sin cambio de comportamiento        |
| `spike/`    | Investigación técnica aislada del código productivo  |

La descripción va en minúsculas, en inglés o español sin tildes, separada por guiones.

```text
feature/RGT-29-initial-migration
fix/RGT-140-arcgis-pagination
spike/RGT-115-route-801-routing
docs/readme-typos
```

## Commits

Los mensajes siguen [Conventional Commits 1.0](https://www.conventionalcommits.org/es/v1.0.0/), con la clave del ticket como alcance.

```text
<tipo>(RGT-<n>): <descripción en imperativo>

[cuerpo opcional: qué cambia y por qué]
```

| Tipo       | Uso                                                       |
| ---------- | --------------------------------------------------------- |
| `feat`     | Funcionalidad nueva                                       |
| `fix`      | Corrección de un defecto                                  |
| `docs`     | Documentación                                             |
| `test`     | Pruebas nuevas o corregidas                               |
| `refactor` | Cambio de código sin alterar comportamiento               |
| `perf`     | Mejora de rendimiento                                     |
| `build`    | Empaquetado, dependencias o sistema de construcción       |
| `ci`       | Configuración de integración continua                     |
| `chore`    | Mantenimiento que no encaja en los tipos anteriores       |
| `data`     | Cambios en catálogos de fuentes o datos versionados       |

Reglas:

- La descripción va en minúsculas, en modo imperativo y sin punto final, con un máximo de 72 caracteres en la primera línea.
- Un commit representa un único cambio lógico; debe poder revertirse de forma aislada.
- Un cambio incompatible se marca con `!` después del alcance y se explica en el pie con `BREAKING CHANGE:`.
- Los commits sin ticket omiten el alcance: `docs: fix broken link in readme`.

```text
feat(RGT-29): add initial schema migration
fix(RGT-140): stop pagination when arcgis returns empty page
docs(RGT-118): add container diagram
```

## Pull requests

- Un pull request por ticket, dirigido a `main`.
- El título sigue el mismo formato que los commits: `feat(RGT-29): add initial schema migration`.
- La descripción usa la plantilla del repositorio: ticket, resumen, cambios, verificación y checklist.
- Mantener el pull request pequeño. Si el ticket es grande, dividirlo en subtareas con pull requests independientes.
- Todas las verificaciones de CI deben estar en verde antes de integrar.
- Los comentarios de revisión se resuelven antes de integrar.

## Integración a main

- `main` está protegida: no se permite push directo, force push ni eliminación.
- La integración se realiza con **rebase and merge**, lo que conserva los commits atómicos de la rama en un historial lineal.
- La rama se elimina automáticamente después de integrarse.

## Definition of Ready

Un ticket puede entrar a un sprint cuando:

- [ ] Tiene un objetivo claro y un alcance acotado.
- [ ] Tiene criterios de aceptación verificables.
- [ ] Pertenece a una épica.
- [ ] Sus dependencias están resueltas o identificadas.
- [ ] Las decisiones técnicas que requiere están registradas como ADR o tienen un ticket previo.
- [ ] Su tamaño permite completarlo dentro del sprint; si no, se divide en subtareas.

## Definition of Done

Un ticket se considera terminado cuando:

- [ ] Los criterios de aceptación se cumplen y se verificaron.
- [ ] El código tiene pruebas para el comportamiento nuevo o modificado.
- [ ] Todas las verificaciones de CI pasan.
- [ ] La documentación afectada está actualizada (README, docs, docstrings).
- [ ] Toda decisión de arquitectura nueva o modificada tiene su ADR en `docs/architecture/adr/`.
- [ ] No quedan secretos, datos crudos ni archivos temporales en el cambio.
- [ ] El pull request está integrado en `main` y la rama eliminada.
- [ ] El ticket de Jira está en `Done` con un comentario de cierre y el enlace al pull request.

## Versionado y releases

El proyecto sigue [Semantic Versioning](https://semver.org/lang/es/). Mientras la versión mayor sea `0`, cualquier versión menor puede introducir cambios incompatibles.

- Cada release se publica como tag anotado `vX.Y.Z` sobre `main`, con su release en GitHub.
- Las versiones se corresponden con las versiones de Jira (_fix versions_) que agrupan los tickets incluidos.
