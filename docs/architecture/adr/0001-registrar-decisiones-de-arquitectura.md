# ADR-0001: Registrar las decisiones de arquitectura como ADR

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-110    |
| Reemplaza a | —          |

## Contexto

RutaGT es un proyecto de largo plazo que podría ser adoptado, auditado o certificado por instituciones públicas. Varias decisiones estructurales (modelo de datos, formatos de intercambio, motor de ruteo, flujo de trabajo) se tomaron en documentos de planificación y conversaciones que no dejan un registro formal, fechado ni trazable.

Sin un registro de decisiones:

- no es posible demostrar por qué el sistema es como es ni quién lo aprobó;
- las decisiones se reabren sin conocer las alternativas ya evaluadas;
- una persona nueva no puede distinguir una decisión vigente de una idea descartada.

## Decisión

Registramos toda decisión de arquitectura significativa como un _Architecture Decision Record_ (ADR) en `docs/architecture/adr/`, siguiendo la plantilla del repositorio.

Una decisión es significativa cuando afecta la estructura del sistema, sus dependencias o tecnologías, sus interfaces externas, el modelo de datos, la seguridad, el cumplimiento legal de los datos o el proceso de ingeniería, o cuando revertirla sería costoso.

Reglas:

1. **Numeración secuencial** de cuatro dígitos y nombre en minúsculas con guiones: `NNNN-titulo-de-la-decision.md`.
2. **Ciclo de vida**: `Propuesto` → `Aceptado` o `Rechazado`. Un ADR aceptado pasa a `Obsoleto` o `Reemplazado por ADR-NNNN` cuando deja de aplicar.
3. **Inmutabilidad**: el contenido de un ADR aceptado no se reescribe. Un cambio de decisión se registra en un ADR nuevo que reemplaza al anterior; en el ADR anterior solo se actualiza el estado.
4. **Trazabilidad**: cada ADR indica fecha, decisores y tickets de Jira relacionados. Se integra mediante pull request, que constituye su registro de aprobación.
5. **Verificación**: cada ADR describe cómo se comprueba su cumplimiento en el repositorio.
6. **Índice**: `docs/architecture/adr/README.md` lista todos los ADR con su estado.
7. **Decisiones previas**: las decisiones tomadas antes de este ADR se registran con la fecha en que se tomaron originalmente, indicada por sus tickets o commits.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Documento único de arquitectura | Una sola lectura | Se reescribe y pierde el historial de cada decisión | No da trazabilidad por decisión |
| Decisiones solo en Jira | Ya integrado al flujo | Disperso, no versionado con el código, inaccesible fuera de Jira | El repositorio debe ser autosuficiente |
| Wiki externa (Confluence) | Edición cómoda | Separada del código y de su revisión por pull request | Pierde la relación con los cambios de código |

## Consecuencias

### Positivas

- Existe un registro auditable, fechado y versionado de por qué el sistema es como es.
- Las decisiones se revisan con el mismo flujo de pull request que el código.
- Facilita la incorporación de nuevas personas y la evaluación por terceros.

### Negativas y riesgos

- Requiere disciplina: una decisión sin ADR queda fuera del registro. La Definition of Done exige actualizar los ADR afectados.

## Verificación

- Existe `docs/architecture/adr/` con plantilla, índice y ADR numerados.
- Cada ADR del índice tiene estado, fecha, decisores y tickets.
- La Definition of Done de `CONTRIBUTING.md` incluye la actualización de ADR.

## Referencias

- Michael Nygard, [_Documenting Architecture Decisions_](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) (2011).
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/).
- ISO/IEC/IEEE 42010:2022, _Software, systems and enterprise — Architecture description_ (registro de decisiones y su justificación).
