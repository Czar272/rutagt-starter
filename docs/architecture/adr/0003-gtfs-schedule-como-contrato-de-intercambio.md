# ADR-0003: Adoptar GTFS Schedule como contrato de intercambio

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-08-15 |
| Decisores   | @Czar272   |
| Tickets     | RGT-12     |
| Reemplaza a | —          |

## Contexto

Los operadores y municipalidades de Guatemala entregan información en formatos heterogéneos: capas ArcGIS, PDF, hojas de cálculo e imágenes. Para planificar viajes, publicar datos y negociar con instituciones se necesita un formato común, conocido por terceros y soportado por motores de ruteo.

## Decisión

Adoptamos **GTFS Schedule** como contrato de intercambio de datos estáticos de transporte:

- La salida publicable del pipeline es un feed GTFS válido, generado desde el modelo canónico ([ADR-0002](0002-postgresql-postgis-como-modelo-canonico.md)).
- Las solicitudes institucionales piden, cuando sea posible, datos en GTFS o en formatos convertibles a GTFS.
- Las extensiones oficiales (`frequencies`, `shapes`, `transfers`, `fares v2`) se usan antes de crear campos propios.
- El modelo interno puede ser más rico que GTFS, pero toda entidad debe poder exportarse a GTFS.

## Alternativas consideradas

| Alternativa    | Ventajas                        | Desventajas                                     | Motivo de descarte                       |
| -------------- | ------------------------------- | ----------------------------------------------- | ---------------------------------------- |
| Formato propio | Libertad total                  | Ningún tercero lo consume; aislaría al proyecto | Contrario a la interoperabilidad buscada |
| NeTEx          | Muy expresivo, estándar europeo | Complejo y con poco soporte en la región        | Costo de adopción desproporcionado       |
| Solo GeoJSON   | Simple para mapas               | No modela horarios, calendarios ni viajes       | Insuficiente para ruteo                  |

## Consecuencias

### Positivas

- Compatibilidad directa con OpenTripPlanner, validadores y aplicaciones de terceros.
- Un entregable concreto y reconocible para instituciones: «un feed GTFS de su sistema».

### Negativas y riesgos

- GTFS exige horarios o frecuencias; los servicios sin horario deben modelarse con frecuencias estimadas e indicarse como tales ([ADR-0017](0017-confianza-explicita-en-itinerarios.md)).

## Verificación

- Los feeds generados pasan el validador oficial de MobilityData (RGT-53).
- El exportador vive en `pipeline/exporters/` y parte del modelo canónico.

## Referencias

- [GTFS Schedule Reference](https://gtfs.org/documentation/schedule/reference/).
- `docs/data/plan-producto-y-datos.md`, sección 4.
