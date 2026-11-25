# Registro de decisiones de arquitectura

Este directorio contiene los _Architecture Decision Records_ (ADR) de RutaGT: cada decisión significativa sobre la arquitectura, los datos, las tecnologías o el proceso de ingeniería, con su contexto, alternativas, consecuencias y forma de verificación.

El proceso está definido en [ADR-0001](0001-registrar-decisiones-de-arquitectura.md).

## Cómo proponer un ADR

1. Copiar [`template.md`](template.md) como `NNNN-titulo-de-la-decision.md` con el siguiente número disponible.
2. Completarlo con estado `Propuesto` y el ticket de Jira asociado.
3. Agregarlo al índice de este archivo.
4. Abrir un pull request. Al integrarse, el estado pasa a `Aceptado` (o `Rechazado`) en el mismo pull request.

## Estados

| Estado                    | Significado                                                   |
| ------------------------- | ------------------------------------------------------------- |
| Propuesto                 | Dirección planificada, pendiente de validación o de su ticket |
| Aceptado                  | Decisión vigente que el proyecto debe cumplir                 |
| Rechazado                 | Evaluada y descartada; se conserva como antecedente           |
| Obsoleto                  | Dejó de aplicar sin un reemplazo directo                      |
| Reemplazado por ADR-NNNN  | Sustituida por una decisión posterior                         |

## Índice

| ADR | Decisión | Estado | Fecha | Tickets |
| --- | -------- | ------ | ----- | ------- |
| [0001](0001-registrar-decisiones-de-arquitectura.md) | Registrar las decisiones de arquitectura como ADR | Aceptado | 2026-11-25 | RGT-110 |
