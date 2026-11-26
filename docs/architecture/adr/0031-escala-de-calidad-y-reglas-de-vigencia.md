# ADR-0031: Adoptar una escala de calidad de datos con reglas de vigencia

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-26 |
| Decisores   | @Czar272   |
| Tickets     | RGT-31     |
| Reemplaza a | —          |

## Contexto

[ADR-0024](0024-confianza-interna-y-estimaciones-como-rangos.md) decidió que la confianza de los datos se usa internamente (ranking, API, reportes) y que la PWA muestra estimaciones como rangos. La migración inicial ([ADR-0029](0029-convenciones-del-esquema-canonico.md), D21) registra la calidad por atributo con el tipo `transit.observation_quality` (`official`, `verified`, `probable`, `unverified`).

Faltaba definir qué significa cada nivel, cómo se asigna y cuánto tiempo sigue siendo válido. Además, la escala no distinguía dos casos que el spike de la ruta 801 y el alcance del MVP necesitan separar:

- un valor **estimado** a partir de supuestos declarados (velocidad comercial de 12–18 km/h, intervalo de 10–20 min), distinto de un valor **inferido** de datos oficiales por un método documentado (la reconciliación de paradas);
- un dato aportado por la **comunidad** y todavía no confirmado.

Un dato verificado en campo o reportado por la comunidad pierde valor con el tiempo: una parada puede moverse y un reporte de cierre deja de aplicar.

## Decisión

### Escala

Seis niveles, ordenados de mayor a menor confianza. El orden del tipo enumerado es el orden de la escala, así que `max()` sobre varios niveles devuelve el **más débil**.

| Nivel        | Significado                                           | Se asigna cuando                                                                                                               |
| ------------ | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `official`   | Publicado por la autoridad o el operador              | El dato proviene sin transformación sustantiva de una fuente `official_open_data`, `official_request` u `operator_partnership` |
| `verified`   | Confirmado de forma independiente                     | Se confirmó en campo, o dos fuentes independientes coinciden, o el operador lo confirmó para un dato de otra fuente            |
| `probable`   | Inferido de datos oficiales con un método documentado | Resulta de un algoritmo reproducible sobre datos oficiales (reconciliación, alineación sobre el trazado)                       |
| `estimated`  | Calculado con supuestos declarados                    | Proviene de un modelo o supuesto (velocidades, intervalos, tiempos de caminata); siempre se presenta como rango                |
| `community`  | Aportado por la comunidad sin confirmar               | Proviene de reportes de usuarios pendientes de verificación                                                                    |
| `unverified` | Sin evidencia suficiente                              | No hay fuente confiable, o existe una incidencia de datos abierta que lo contradice                                            |

### Reglas

1. **Por atributo**: la calidad se registra para cada atributo cuyas fuentes difieren (ubicación de la parada, secuencia del patrón, trazado), con la fecha en que se evaluó.
2. **Eslabón más débil**: un valor derivado (un tiempo de viaje, un itinerario) tiene la calidad del más débil de sus insumos.
3. **Vigencia**: cada nivel tiene una antigüedad máxima. Al vencer, la calidad **efectiva** baja un nivel según la tabla; el dato almacenado no se modifica, se recalcula al consultar.

   | Nivel        | Antigüedad máxima                                         | Al vencer pasa a |
   | ------------ | --------------------------------------------------------- | ---------------- |
   | `official`   | Mientras la fuente esté vigente (`valid_to` de la fuente) | `probable`       |
   | `verified`   | 365 días desde la verificación                            | `probable`       |
   | `probable`   | Sin vencimiento; se recalcula al cambiar sus insumos      | —                |
   | `estimated`  | Sin vencimiento; se recalcula al cambiar los supuestos    | —                |
   | `community`  | 30 días desde el reporte                                  | `unverified`     |
   | `unverified` | —                                                         | —                |

4. **Conflictos**: una incidencia abierta en `provenance.data_issue` sobre un atributo lo deja como `unverified` hasta resolverla.
5. **Ascenso**: un dato solo sube de nivel con nueva evidencia (fuente oficial, verificación en campo o confirmación independiente), nunca por paso del tiempo.

### Representación en la base de datos

- `transit.observation_quality` incorpora `estimated` y `community` en su posición de la escala.
- `provenance.quality_rule` guarda la antigüedad máxima y el nivel de degradación de cada nivel; cambiar una regla es un cambio de datos, no de código.
- Cada atributo con calidad tiene su fecha de evaluación: `stop.location_assessed_at`, `pattern_stop.sequence_assessed_at` y `shape.quality_assessed_at`.
- `public.rutagt_effective_quality(calidad, evaluada_en, vigencia_fuente, momento)` devuelve la calidad efectiva aplicando las reglas.

## Alternativas consideradas

| Alternativa                                          | Ventajas          | Desventajas                                                                         | Motivo de descarte                                          |
| ---------------------------------------------------- | ----------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Mantener cuatro niveles                              | Sin migración     | Mezcla estimaciones con inferencias y reportes comunitarios con datos sin evidencia | Pierde distinciones que el ranking y los reportes necesitan |
| Puntaje numérico continuo (0–1)                      | Granularidad      | Falsa precisión; difícil de explicar y auditar                                      | Una escala ordinal es suficiente y explicable               |
| Degradar el dato almacenado con un proceso periódico | Consultas simples | Modifica datos sin evidencia nueva; depende de un proceso programado                | La calidad efectiva se calcula al consultar                 |
| Vigencia fija en código                              | Simple            | Cambiar una regla requiere desplegar                                                | Las reglas viven en una tabla                               |

## Consecuencias

### Positivas

- El ranking de itinerarios (RGT-60) y los reportes de calidad (RGT-40) tienen una escala común y ordenable.
- Las verificaciones de campo y los reportes comunitarios caducan sin intervención manual.
- La distinción entre `probable` y `estimated` hace explícito qué valores deben mostrarse como rangos (ADR-0024).

### Negativas y riesgos

- Los tipos enumerados de PostgreSQL no permiten quitar valores; revertir la migración convierte `estimated` en `probable` y `community` en `unverified`.
- Las antigüedades máximas son una primera estimación y deben revisarse con datos de campo.

## Verificación

- Pruebas de integración comprueban el orden de la escala, que cada nivel tiene su regla y que la calidad efectiva se degrada al vencer.
- Las reglas de asignación se aplicarán en la normalización (Sprint 6) y en las validaciones de calidad (RGT-40).

## Referencias

- [ADR-0024](0024-confianza-interna-y-estimaciones-como-rangos.md).
- [Revisión del esquema canónico](../canonical-schema-review.md), D21.
- [Spike de la ruta 801](../../research/spike-ruta-801.md).
