# ADR-0005: Usar Python para el pipeline de datos

| Campo       | Valor          |
| ----------- | -------------- |
| Estado      | Aceptado       |
| Fecha       | 2026-08-15     |
| Decisores   | @Czar272       |
| Tickets     | RGT-15, RGT-19 |
| Reemplaza a | —              |

## Contexto

El pipeline debe descargar servicios ArcGIS y páginas HTML, transformar geometrías, validar calidad, cargar PostGIS y exportar GTFS. Más adelante incluirá modelos de predicción de tiempos de llegada. Se necesita un lenguaje con ecosistema geoespacial y de datos maduro, fácil de mantener y conocido por perfiles de datos y del sector público.

## Decisión

Usamos **Python 3.10 o posterior** como lenguaje del pipeline de datos (collectors, normalizers, validators y exporters).

El recolector inicial usa **únicamente la biblioteca estándar** para minimizar dependencias en la etapa de adquisición. Las etapas posteriores pueden incorporar dependencias de terceros cuando aporten valor claro; su gestión, empaquetado y herramientas de calidad se definen en RGT-122 y RGT-123.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Node.js / TypeScript | Mismo lenguaje que un posible frontend | Ecosistema geoespacial y científico menos maduro | Python domina el procesamiento de datos GIS |
| Java / Kotlin | Mismo ecosistema que OpenTripPlanner | Más verboso para scripts de datos | Mayor costo de desarrollo para el pipeline |
| SQL puro en PostGIS | Sin capa intermedia | Difícil para descargas, HTML y validaciones complejas | Insuficiente como único lenguaje |

## Consecuencias

### Positivas

- Acceso a librerías geoespaciales y de datos (GeoPandas, Shapely, pyproj, gtfs-kit) cuando sean necesarias.
- Las pruebas se escriben en el mismo lenguaje que el pipeline.

### Negativas y riesgos

- Rendimiento inferior a lenguajes compilados en volúmenes grandes; aceptable para la escala metropolitana prevista.
- Requiere gestionar versiones y dependencias de forma reproducible (RGT-123).

## Verificación

- `pipeline/collectors/collect.py` y `tests/` están escritos en Python y se ejecutan con `python -m unittest discover -s tests`.

## Referencias

- `docs/data/plan-producto-y-datos.md`, sección 9.
