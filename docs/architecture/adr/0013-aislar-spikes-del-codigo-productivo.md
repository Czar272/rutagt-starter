# ADR-0013: Aislar los spikes experimentales del código productivo

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-08-22 |
| Decisores   | @Czar272   |
| Tickets     | RGT-115    |
| Reemplaza a | —          |

## Contexto

Algunas preguntas técnicas deben responderse antes de comprometer una implementación definitiva; por ejemplo, hasta dónde se puede construir un itinerario con los datos abiertos disponibles (spike de la ruta 801). Si el código exploratorio se mezcla con el pipeline productivo, introduce atajos, dependencias y supuestos no validados.

## Decisión

Los spikes se desarrollan en **`prototype/<tema>/`**, aislados del pipeline y del esquema productivos:

- El código de `prototype/` no se importa desde `pipeline/` ni desde servicios.
- Puede leer datos de `data/raw/` o `data/normalized/`, pero solo escribe en su propio directorio `output/`.
- Cada spike tiene un ticket con objetivo y alcance explícitos, y termina con un informe de hallazgos en `docs/research/`.
- Lo que se decida conservar se reimplementa en el código productivo mediante tickets ordinarios, con pruebas y revisión.
- Las ramas de spikes usan el prefijo `spike/`.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Experimentar en el pipeline | Reutilización inmediata | Contamina el código productivo con supuestos no validados | Riesgo de deuda técnica |
| Repositorio separado | Aislamiento total | Pierde acceso directo a datos y contexto | Fricción innecesaria |

## Consecuencias

### Positivas

- Se puede investigar rápido sin comprometer la calidad del código productivo.
- Los hallazgos quedan documentados aunque el código del spike se descarte.

### Negativas y riesgos

- La lógica útil del spike debe reescribirse; se acepta como costo del aislamiento.

## Verificación

- El código del spike vive en `prototype/` y no es importado por `pipeline/`.
- El informe de cierre existe en `docs/research/` (RGT-133).

## Referencias

- `prototype/routing/`.
