# ADR-0002: Usar PostgreSQL con PostGIS como modelo canónico de datos

| Campo       | Valor          |
| ----------- | -------------- |
| Estado      | Aceptado       |
| Fecha       | 2026-08-15     |
| Decisores   | @Czar272       |
| Tickets     | RGT-13, RGT-27 |
| Reemplaza a | —              |

## Contexto

RutaGT integra información de múltiples operadores y fuentes con calidad variable: geometrías de rutas, paradas, secuencias, calendarios, tarifas, transbordos, observaciones en tiempo real y reportes comunitarios. Cada registro debe conservar su procedencia, vigencia y nivel de confianza.

El modelo de datos necesita:

- operaciones espaciales (proximidad a paradas, intersección con recorridos, distancias de caminata);
- integridad referencial entre rutas, variantes, paradas y viajes;
- representar datos incompletos o no verificados sin perder el dato original;
- poder importar y exportar GTFS ([ADR-0003](0003-gtfs-schedule-como-contrato-de-intercambio.md)) sin quedar limitado por él.

## Decisión

Usamos **PostgreSQL con la extensión PostGIS** como base de datos canónica de RutaGT. El esquema canónico vive en `database/schema/canonical.sql` y se basa en las entidades de GTFS, ampliadas con procedencia (`data_source`, `source_record`), calidad (`observation_quality`), estado de vigencia y entidades de tiempo real.

Todas las geometrías se almacenan en **EPSG:4326 (WGS 84)**, con índices GiST.

La versión de referencia es **PostgreSQL 17 con PostGIS 3.5**, fijada por la imagen `postgis/postgis:17-3.5` ([ADR-0010](0010-entorno-local-reproducible-con-docker-compose.md)).

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Archivos GTFS como única fuente | Estándar, simple | No representa procedencia, incertidumbre ni datos parciales | GTFS es un formato de salida, no un modelo de trabajo |
| MongoDB u otra base documental | Esquema flexible | Integridad referencial y consultas espaciales más débiles | El dominio es fuertemente relacional |
| SpatiaLite / GeoPackage | Sin servidor | No apto para concurrencia ni para una API en producción | Limita la evolución a servicio |
| Base espacial comercial | Soporte del proveedor | Costo de licencias y dependencia | Incompatible con un proyecto de bajo costo y abierto |

## Consecuencias

### Positivas

- Consultas espaciales y relacionales en un mismo motor maduro, abierto y ampliamente usado en el sector público.
- La procedencia es parte del modelo, no un anexo.
- OpenTripPlanner, herramientas GIS (QGIS) y librerías Python se integran de forma nativa.

### Negativas y riesgos

- Requiere operar un servidor de base de datos en todos los entornos.
- El esquema canónico es más rico que GTFS, por lo que la exportación requiere una capa de transformación explícita.

## Verificación

- `compose.yaml` levanta `postgis/postgis:17-3.5` con healthcheck.
- `database/schema/canonical.sql` declara `CREATE EXTENSION postgis` y usa `geometry(..., 4326)`.

## Referencias

- `docs/data/plan-producto-y-datos.md`, secciones 4 y 9.
- [PostGIS](https://postgis.net/).
