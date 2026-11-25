# ADR-0004: Separar los datos en capas inmutables con procedencia obligatoria

| Campo       | Valor                          |
| ----------- | ------------------------------ |
| Estado      | Aceptado                       |
| Fecha       | 2026-08-15                     |
| Decisores   | @Czar272                       |
| Tickets     | RGT-14, RGT-16, RGT-25         |
| Reemplaza a | —                              |

## Contexto

Las fuentes oficiales cambian sin aviso, pueden contener errores de codificación o de ubicación y suelen carecer de una licencia explícita. Si los datos se corrigen sobre el archivo original, se pierde la evidencia de qué dijo la fuente, cuándo y con qué contenido exacto. Para una plataforma que podría ser auditada por instituciones, cada dato publicado debe poder rastrearse hasta su origen.

## Decisión

Organizamos los datos en **capas sucesivas que nunca sobrescriben a la anterior**:

```text
data/raw → data/staging → data/normalized → data/gtfs → data/published
```

| Capa         | Contenido                                                    |
| ------------ | ------------------------------------------------------------ |
| `raw`        | Respuesta original de la fuente, sin modificaciones          |
| `staging`    | Datos en preparación o revisión manual                       |
| `normalized` | Datos depurados con identificadores y estructura comunes     |
| `gtfs`       | Feeds GTFS de trabajo                                        |
| `published`  | Artefactos validados y aptos para distribución               |

Toda descarga genera un archivo `.provenance.json` con: fuente, autoridad, URL final, fecha UTC, checksum SHA-256, número de registros, licencia declarada y advertencias de calidad. Cada ejecución del recolector genera un `run_manifest.json`.

Las correcciones se aplican en capas posteriores y deben registrar la evidencia que las justifica. `data/raw/` se excluye del control de versiones.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Corregir en el lugar | Menos archivos | Destruye evidencia; no reproducible | Incompatible con la trazabilidad requerida |
| Versionar datos crudos en Git | Historial completo | Repositorio pesado; posibles restricciones de licencia | Se reemplaza con checksums y snapshots fuera de Git |

## Consecuencias

### Positivas

- Cualquier dato publicado se puede rastrear hasta su descarga original.
- Los cambios en las fuentes se detectan comparando checksums.
- Las ejecuciones son reproducibles y auditables.

### Negativas y riesgos

- Mayor uso de almacenamiento.
- Los snapshots crudos fuera de Git requieren una política de respaldo y versionado (RGT-32, RGT-108).

## Verificación

- `pipeline/collectors/collect.py` escribe `.provenance.json` por fuente y `run_manifest.json` por ejecución.
- `.gitignore` excluye `data/raw/`.
- El esquema canónico conserva `raw_payload` y `checksum` en `source_record`.

## Referencias

- `README.md`, sección «Uso».
- `database/schema/canonical.sql`, tablas `data_source` y `source_record`.
