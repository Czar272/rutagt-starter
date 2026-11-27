# Base de datos canónica

PostgreSQL 17 + PostGIS 3.5 ([ADR-0002](../docs/architecture/adr/0002-postgresql-postgis-como-modelo-canonico.md)). El esquema se define **solo por migraciones** de Alembic en SQL explícito ([ADR-0030](../docs/architecture/adr/0030-migraciones-con-alembic-en-sql-explicito.md)) y sigue las convenciones del [ADR-0029](../docs/architecture/adr/0029-convenciones-del-esquema-canonico.md).

## Uso

La conexión se lee de las variables `RUTAGT_DB_*` (ver `.env.example`); el código no carga `.env`, así que se pasa con `--env-file`:

```powershell
docker compose up -d                                   # PostGIS local
uv run --env-file .env alembic upgrade head            # crear o actualizar el esquema
uv run --env-file .env alembic current                 # versión aplicada
uv run --env-file .env alembic history                 # revisiones disponibles
uv run --env-file .env alembic downgrade -1            # revertir la última revisión
```

## Organización

```text
alembic.ini                              Configuración (raíz del repositorio)
database/migrations/env.py               Conexión y ejecución de las migraciones
database/migrations/script.py.mako       Plantilla de revisiones nuevas
database/migrations/versions/
  r0001_initial_schema.py                Revisión
  r0001_initial_schema/upgrade.sql       SQL que aplica
  r0001_initial_schema/downgrade.sql     SQL que revierte
  r0002_quality_scale_levels/            Niveles estimated y community (ADR-0031)
  r0003_quality_validity_rules/          Reglas de vigencia de la calidad (ADR-0031)
  r0004_canonical_load/                  Procedencia por entidad y clave de incidencias (ADR-0035)
```

| Esquema      | Contenido                                                               |
| ------------ | ----------------------------------------------------------------------- |
| `provenance` | Fuentes, registros originales, su enlace con cada entidad e incidencias |
| `transit`    | Red y servicio programado (compatible con GTFS)                         |
| `realtime`   | Observaciones, alertas y predicciones                                   |
| `community`  | Reportes de la comunidad                                                |
| `public`     | Solo la extensión PostGIS, funciones `rutagt_*` y `alembic_version`     |

Funciones auxiliares: `rutagt_is_entity_id(id, tipo)` valida identificadores `<agencia>:<tipo>:<código>`, `rutagt_distance_m(a, b)` mide en metros, `rutagt_set_updated_at()` mantiene `updated_at` y `rutagt_effective_quality(nivel, evaluado_en, vigencia_fuente, momento)` aplica las reglas de vigencia de la calidad.

## Carga de la red canónica

`rutagt-load` escribe `data/normalized/<snapshot>/canonical.json` (de `rutagt-canonical`) en una sola transacción ([ADR-0035](../docs/architecture/adr/0035-constructor-canonico-y-carga-idempotente.md)):

```powershell
uv run rutagt-canonical                       # staging -> data/normalized/<snapshot>/
uv run --env-file .env rutagt-load            # normalized -> PostGIS
```

- Recargar el mismo dataset no modifica ninguna fila: solo se actualiza lo que cambió, y `updated_at` y `loaded_by_run` reflejan el último cambio real.
- `provenance.entity_source_record` enlaza cada entidad con todos sus registros originales; `source_record` no repite registros sin cambios.
- Lo que una fuente deja de publicar pasa a `status = 'retired'`; nunca se borra.
- Las incidencias del pipeline se identifican por `issue_key` y conservan su estado de curación; las abiertas que ya no se detectan pasan a `resolved`.

```sql
-- Registros de origen de un andén
SELECT r.external_id, r.raw_payload
FROM provenance.entity_source_record e
JOIN provenance.source_record r USING (source_record_id)
WHERE e.entity_type = 'stop' AND e.entity_id = 'transmetro:stop:bolivar.1';
```

## Calidad de los datos

La escala `transit.observation_quality` ([ADR-0031](../docs/architecture/adr/0031-escala-de-calidad-y-reglas-de-vigencia.md)) va de mayor a menor confianza: `official`, `verified`, `probable`, `estimated`, `community`, `unverified`. Por eso `max()` sobre varios niveles da el más débil (regla del eslabón más débil).

Las reglas de vigencia están en `provenance.quality_rule`, como datos: cambiarlas no requiere una migración. La calidad efectiva se calcula al consultar:

```sql
SELECT stop_id,
       public.rutagt_effective_quality(s.location_quality, s.location_assessed_at, d.valid_to)
FROM transit.stop s
LEFT JOIN provenance.data_source d USING (source_id);
```

## Agregar una migración

1. `uv run --env-file .env alembic revision -m "descripcion corta"` crea `rNNNN_descripcion_corta.py`; usar un identificador secuencial (`--rev-id 0002`).
2. Crear la carpeta homónima con `upgrade.sql` y `downgrade.sql`.
3. Seguir el ADR-0029: índice por clave foránea, `ON DELETE` explícito, `CHECK`, `created_at`/`updated_at` con el trigger `set_updated_at` en tablas nuevas.
4. Ejecutar `uv run --env-file .env pytest -m integration`: las pruebas verifican las convenciones sobre el esquema completo.

**Nunca modificar una migración ya integrada en `main`**; cualquier cambio es una revisión nueva.

El SQL se envía al controlador sin parámetros, así que `:` y `%` pueden usarse libremente; el modo `alembic upgrade --sql` no está soportado.

## Pruebas

`tests/db/test_migrations.py` (marcador `integration`) crea una base temporal por prueba, aplica todas las migraciones, verifica esquemas, índices de claves foráneas, auditoría, SRID y restricciones, revierte hasta la base y vuelve a aplicar. En CI corre en el trabajo «Pruebas de integración» contra un servicio PostGIS.
