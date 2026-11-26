# ADR-0029: Adoptar convenciones para el esquema canónico de la base de datos

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-28     |
| Reemplaza a | —          |

## Contexto

[ADR-0002](0002-postgresql-postgis-como-modelo-canonico.md) adoptó PostgreSQL con PostGIS como modelo canónico. Antes de convertir `database/schema/canonical.sql` en la migración inicial (RGT-29), la [revisión del esquema](../canonical-schema-review.md) encontró, entre otros: 44 de 52 claves foráneas sin índice, ninguna columna `created_at`, `updated_at` sin mantenimiento automático, ausencia de `location_type` para estaciones, trazados `MultiLineString` sin orden garantizado, calidad registrada solo a nivel de entidad y todas las tablas en el esquema `public`. Sin convenciones explícitas, cada tabla nueva repetiría esos problemas.

## Decisión

Toda tabla del modelo canónico sigue estas convenciones:

| Aspecto                          | Convención                                                                                                                                                |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Esquemas                         | `provenance` (fuentes y registros originales), `transit` (red y servicio), `realtime` (observaciones y predicciones), `community` (reportes)              |
| Nombres                          | `snake_case`, tablas en singular, claves foráneas `<entidad>_id`                                                                                          |
| Identificadores de la red        | `text` con formato estable `<agencia>:<tipo>:<código>` validado por `CHECK`; el identificador de la fuente se guarda en la procedencia                    |
| Identificadores de observaciones | `bigint GENERATED ALWAYS AS IDENTITY`                                                                                                                     |
| Índices                          | Un índice por cada clave foránea que no esté cubierta por otro índice; GiST en toda geometría                                                             |
| Integridad referencial           | `ON DELETE RESTRICT` por defecto; `CASCADE` solo en tablas de detalle de su entidad padre                                                                 |
| Restricciones                    | `CHECK` para rangos de vigencia, valores de GTFS, colores y relaciones entre columnas                                                                     |
| Valores enumerados               | `ENUM` para conjuntos estables propios del proyecto; `smallint` con `CHECK` para valores definidos por GTFS                                               |
| Auditoría                        | `created_at` y `updated_at` (`timestamptz`, `DEFAULT now()`) con trigger común; `loaded_by_run` con el `run_id` del pipeline en las tablas que este carga |
| Geometrías                       | EPSG:4326; distancias y áreas con `geography` o en EPSG:32615 (UTM 15N)                                                                                   |
| Trazados                         | `LineString` continuo por patrón                                                                                                                          |
| Calidad                          | `observation_quality` por atributo cuando las fuentes difieren por atributo (p. ej. secuencia y ubicación de una parada)                                  |
| Discrepancias                    | Registro en una tabla de incidencias de datos con su evidencia                                                                                            |
| GTFS                             | Toda entidad debe poder exportarse a GTFS Schedule; incluir lo necesario para `feed_info` y atribuciones                                                  |

## Alternativas consideradas

| Alternativa                                | Ventajas                        | Desventajas                                                   | Motivo de descarte                                    |
| ------------------------------------------ | ------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------- |
| Mantener el esquema actual en `public`     | Sin trabajo adicional           | Problemas de rendimiento, auditoría y exportación a GTFS      | La revisión mostró deficiencias de severidad alta     |
| Claves `uuid` para toda la red             | Únicas globalmente              | Ilegibles, sin relación con GTFS, más difíciles de depurar    | Se prefieren identificadores estables y legibles      |
| Tablas de catálogo en lugar de `ENUM`      | Valores editables sin migración | Más JOIN y claves foráneas para conjuntos que casi no cambian | Se usan solo cuando los valores los define un tercero |
| Historial completo con tablas de auditoría | Trazabilidad total de cambios   | Complejidad prematura                                         | Se evaluará con el panel de correcciones (RGT-94)     |

## Consecuencias

### Positivas

- La migración inicial nace con integridad, índices y auditoría consistentes.
- La exportación a GTFS no requiere transformaciones ad hoc para estaciones, trazados ni atribuciones.
- La calidad por atributo y las incidencias de datos conservan lo aprendido en el spike de la ruta 801.

### Negativas y riesgos

- Más columnas y restricciones que mantener en cada tabla.
- Los identificadores con formato exigen normalizar los códigos de cada fuente antes de cargar.

## Verificación

- La migración inicial (RGT-29) crea los esquemas `provenance`, `transit`, `realtime` y `community`.
- Pruebas de integración comprueban que no hay claves foráneas sin índice y que las tablas de catálogo tienen `created_at`, `updated_at` y su trigger.
- Las restricciones rechazan datos inválidos en pruebas de integración.

## Referencias

- [Revisión del esquema canónico](../canonical-schema-review.md).
- [GTFS Schedule Reference](https://gtfs.org/documentation/schedule/reference/).
- [PostgreSQL — Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).
