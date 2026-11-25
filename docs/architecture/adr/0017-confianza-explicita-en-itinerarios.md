# ADR-0017: Mostrar la incertidumbre y el nivel de confianza en cada itinerario

| Campo       | Valor                  |
| ----------- | ---------------------- |
| Estado      | Reemplazado por [ADR-0024](0024-confianza-interna-y-estimaciones-como-rangos.md) |
| Fecha       | 2026-08-15             |
| Decisores   | @Czar272               |
| Tickets     | RGT-31, RGT-61, RGT-85 |
| Reemplaza a | —                      |

## Contexto

Gran parte del transporte público guatemalteco no publica horarios; las frecuencias, los tiempos de recorrido y algunas ubicaciones de paradas serán estimados o inferidos. Presentar una hora exacta de llegada basada en datos estimados generaría expectativas falsas, pérdida de confianza y, en el peor caso, decisiones inseguras para el usuario.

## Decisión

La precisión, el origen del dato y la incertidumbre son **parte del producto**:

- Cada dato del modelo tiene un nivel de calidad (`official`, `verified`, `probable`, `unverified`) y su fuente.
- Los itinerarios muestran **rangos** (por ejemplo, «pasa cada 12–18 minutos») en lugar de horas exactas cuando no hay horario oficial.
- Las horas de salida recomendadas se calculan con percentiles altos (P90) de tiempo de viaje cuando existan datos observados.
- Cada itinerario muestra un **nivel de confianza** y la fecha de la última verificación de sus datos.
- Un dato inferido nunca se presenta como oficial.

Los niveles concretos y sus reglas de cálculo se definen en RGT-31.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Mostrar horas exactas siempre | Interfaz más simple | Falsa precisión y pérdida de confianza | Engañoso para el usuario |
| Ocultar rutas sin horario oficial | Solo datos seguros | Dejaría fuera la mayor parte del sistema | Cobertura insuficiente |

## Consecuencias

### Positivas

- Recomendaciones honestas y defendibles ante usuarios e instituciones.
- Incentiva conseguir datos oficiales: su efecto en la confianza es visible.

### Negativas y riesgos

- La interfaz debe comunicar incertidumbre de forma comprensible.

## Verificación

- `database/schema/canonical.sql` define `observation_quality` y vincula registros con `data_source`.
- Las respuestas de planificación de la API incluyen nivel de confianza y fuentes (RGT-61, RGT-67).

## Referencias

- `docs/data/plan-producto-y-datos.md`, secciones 2, 7 y 12.
