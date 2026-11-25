# ADR-0012: Gestionar el trabajo con Scrum de sprints semanales en Jira

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-116    |
| Reemplaza a | —          |

## Contexto

El backlog inicial se organizó en sprints de dos semanas, uno por épica. En la práctica, el ritmo de trabajo permite cerrar objetivos en menos tiempo y el primer sprint activo quedó vencido sin cerrarse. Se necesita una cadencia que refleje el avance real y genere evidencia del proceso (objetivos, reportes de sprint, velocidad).

## Decisión

- El trabajo se gestiona en el proyecto **RGT** de Jira con un board **Scrum**.
- Los **sprints duran una semana** y tienen un objetivo explícito; no corresponden uno a uno con las épicas.
- Las **épicas** agrupan resultados de producto; los **tickets** (Task) son unidades entregables; las **subtareas** dividen tickets grandes.
- Los estados son `To Do`, `In Progress`, `IN REVIEW`, `BLOCKED` y `Done`, con las reglas de `CONTRIBUTING.md`.
- Al cerrar un ticket se deja un comentario con lo realizado, su verificación y el enlace al pull request.
- Las releases se agrupan con versiones de Jira alineadas con los tags del repositorio.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Sprints de dos semanas por épica | Plan inicial existente | No refleja el ritmo real; sprints vencidos | Reemplazado por cadencia semanal |
| Kanban | Flujo continuo, menos ceremonia | Sin objetivos ni reportes por iteración | Se prefiere evidencia por iteración |
| Board nuevo | Empezar desde cero | Pierde historial y continuidad de claves | Se reorganizó el board existente |

## Consecuencias

### Positivas

- Objetivos semanales verificables y reportes de sprint como evidencia del proceso.
- Trazabilidad entre Jira, ramas, commits y pull requests ([ADR-0011](0011-flujo-git-con-ramas-por-ticket.md)).

### Negativas y riesgos

- La planificación semanal requiere revisar y ajustar el backlog con frecuencia.

## Verificación

- Board Scrum del proyecto RGT con sprints semanales y objetivo declarado.
- Los tickets cerrados contienen comentario de cierre y enlace al pull request.

## Referencias

- `CONTRIBUTING.md`, secciones «Flujo de trabajo», «Definition of Ready» y «Definition of Done».
