# ADR-0024: Usar la confianza de los datos internamente y mostrar las estimaciones como rangos

| Campo       | Valor                  |
| ----------- | ---------------------- |
| Estado      | Aceptado               |
| Fecha       | 2026-11-25             |
| Decisores   | @Czar272               |
| Tickets     | RGT-117, RGT-61        |
| Reemplaza a | ADR-0017               |

## Contexto

[ADR-0017](0017-confianza-explicita-en-itinerarios.md) estableció que cada itinerario mostraría a la persona usuaria la fuente, la fecha de verificación y el nivel de confianza de sus datos. Al revisar el alcance del MVP se identificó un riesgo de producto: etiquetas de confianza o advertencias sobre la calidad de los datos en cada viaje pueden hacer que las personas perciban la aplicación como poco fiable y dejen de usarla, aun cuando la recomendación sea la mejor disponible.

Al mismo tiempo, se mantienen los problemas que motivaron ADR-0017:

- muchos servicios no publican horarios, por lo que los tiempos son estimados;
- presentar una hora exacta que no se cumple daña la confianza más que un rango honesto;
- las licencias de las fuentes (OpenStreetMap, datos municipales) exigen atribución;
- el proyecto necesita conocer la calidad de cada dato para ordenar alternativas, priorizar validaciones y solicitar datos a las instituciones.

## Decisión

Separamos el **uso interno** de la confianza de su **presentación** en la aplicación:

**Uso interno (se conserva):**

- Cada dato del modelo mantiene su fuente, vigencia y nivel de calidad (`official`, `verified`, `probable`, `unverified`).
- El ranking de itinerarios usa la confianza como criterio: entre opciones similares, prefiere las basadas en datos más confiables y penaliza transbordos con tiempos inciertos.
- La API expone la confianza y la procedencia en sus respuestas para uso interno, de calidad y de instituciones; la PWA no la muestra en el itinerario.
- Los reportes de calidad para instituciones incluyen la confianza por ruta y parada.

**Presentación en la PWA:**

- No se muestran etiquetas de confianza, porcentajes de certeza ni advertencias sobre la calidad de los datos en los itinerarios.
- Los valores estimados se expresan como **rangos naturales** («pasa cada 10–15 min», «llegas entre 7:30 y 7:45»), nunca como horas exactas ficticias. Solo se muestra una hora puntual cuando proviene de un horario oficial.
- Las fuentes, la atribución exigida por las licencias y la fecha de actualización de los datos se presentan en una sección **«Acerca de los datos»**, accesible desde la aplicación.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Mantener ADR-0017 (confianza visible por itinerario) | Máxima transparencia | Riesgo de desconfianza y abandono | Se prioriza la adopción por parte de las personas usuarias |
| Confianza totalmente oculta, con horas puntuales | Interfaz más simple | Horas estimadas que parecen exactas y no se cumplen | Daña la confianza más que un rango |

## Consecuencias

### Positivas

- La interfaz transmite seguridad sin prometer precisión que los datos no tienen.
- Se conserva todo el valor de la confianza para el ranking, la calidad de datos y la relación con instituciones.
- Se cumplen las obligaciones de atribución de las licencias.

### Negativas y riesgos

- Las personas no ven directamente qué partes de un itinerario son estimadas; se mitiga con los rangos y con un ranking que prefiere datos confiables.
- Requiere disciplina en la PWA para no mostrar horas puntuales derivadas de estimaciones.

## Verificación

- La respuesta de planificación de la API incluye confianza y procedencia (RGT-61, RGT-67).
- Las pruebas de la PWA verifican que los tiempos estimados se presentan como rangos (RGT-74).
- La sección «Acerca de los datos» lista las fuentes con su atribución y fecha de actualización.

## Referencias

- [ADR-0017](0017-confianza-explicita-en-itinerarios.md) (reemplazado).
- [Alcance del MVP](../../product/alcance-mvp.md).
- [OpenStreetMap — Copyright and License](https://www.openstreetmap.org/copyright).
