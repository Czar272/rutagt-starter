# ADR-0011: Usar un flujo Git basado en main con ramas por ticket

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-125    |
| Reemplaza a | —          |

## Contexto

Hasta noviembre de 2026 los cambios se integraban directamente en `main`, con mensajes de commit sin un formato uniforme. Para un proyecto que aspira a ser auditado o adoptado por instituciones, cada cambio debe poder rastrearse hasta el requerimiento que lo motivó y haber pasado por verificaciones antes de integrarse.

## Decisión

Adoptamos un flujo **basado en `main` con ramas de corta duración por ticket**:

- `main` es la única rama de larga duración y está protegida: sin push directo, sin force push, sin eliminación y con historial lineal.
- Cada ticket se desarrolla en una rama `<tipo>/RGT-<n>-<descripcion>` y se integra mediante pull request.
- Los mensajes siguen **Conventional Commits** con la clave del ticket como alcance: `feat(RGT-29): ...`.
- La integración usa **rebase and merge**, conservando los commits atómicos en un historial lineal.
- El propietario del repositorio revisa cada pull request antes de integrarlo.
- Las verificaciones de CI serán obligatorias para integrar (RGT-107).

El detalle operativo está en `CONTRIBUTING.md`.

## Alternativas consideradas

| Alternativa                       | Ventajas                      | Desventajas                                  | Motivo de descarte                                 |
| --------------------------------- | ----------------------------- | -------------------------------------------- | -------------------------------------------------- |
| Git Flow (`develop`, `release/*`) | Separación formal de releases | Ramas de larga duración y fusiones complejas | Innecesario para entregas continuas                |
| Commits directos a `main`         | Rápido                        | Sin revisión ni verificación previa          | No auditable                                       |
| Squash merge                      | Historial compacto            | Pierde los commits atómicos del ticket       | Se prefiere granularidad para control de versiones |

## Consecuencias

### Positivas

- Trazabilidad completa: ticket → rama → commits → pull request → `main`.
- Historial lineal, legible y fácil de revertir por commit.
- Base para generar changelogs automáticamente a partir de Conventional Commits.

### Negativas y riesgos

- Cada cambio, incluso menor, requiere un pull request.
- El rebase exige mantener las ramas actualizadas respecto de `main`.

## Verificación

- Ruleset «Protección de main» activo en GitHub.
- Configuración del repositorio: solo _rebase merge_ habilitado y borrado automático de ramas.
- `CONTRIBUTING.md` documenta el flujo.

## Referencias

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/es/v1.0.0/).
- [Trunk Based Development](https://trunkbaseddevelopment.com/).
