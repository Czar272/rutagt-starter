# ADR-0030: Gestionar las migraciones del esquema con Alembic y SQL explícito

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-26 |
| Decisores   | @Czar272   |
| Tickets     | RGT-29     |
| Reemplaza a | —          |

## Contexto

El esquema canónico ([ADR-0002](0002-postgresql-postgis-como-modelo-canonico.md), convenciones en [ADR-0029](0029-convenciones-del-esquema-canonico.md)) existía como un único archivo `canonical.sql` que había que cargar a mano con `psql`. Así no se puede saber qué versión del esquema tiene una base, aplicar cambios de forma incremental ni reconstruir una base vacía de forma reproducible, que es el criterio de aceptación de RGT-29.

Restricciones:

- El proyecto es Python 3.12 gestionado con uv ([ADR-0019](0019-herramientas-de-entorno-y-calidad-de-codigo.md)) y la API será FastAPI ([ADR-0022](0022-fastapi-para-la-api.md)).
- El esquema usa PostGIS, varios esquemas, tipos enumerados, triggers y restricciones `CHECK`: la generación automática de migraciones a partir de modelos ORM no los representa bien.
- Las migraciones deben ejecutarse igual en Windows, Linux y CI sin instalar herramientas fuera de uv.

## Decisión

- **Alembic** gestiona las migraciones, con **psycopg 3** como controlador.
- Las migraciones se escriben en **SQL explícito** (`op.execute`); no se usa `autogenerate` ni se requieren modelos ORM. El SQL de cada migración vive en un archivo `.sql` junto a su revisión para poder revisarlo como SQL.
- Las migraciones viven en `database/migrations/`; la configuración en `alembic.ini` en la raíz.
- **Una migración aplicada no se modifica**: cada cambio es una revisión nueva. Cada revisión tiene `upgrade` y `downgrade`.
- Cada migración corre en su propia transacción (PostgreSQL admite DDL transaccional).
- La conexión se construye desde las variables `RUTAGT_DB_*` (`rutagt.db.settings`); el código no lee `.env`, se pasa con `uv run --env-file .env`.
- `database/schema/canonical.sql` deja de ser fuente de verdad: el esquema es el resultado de aplicar las migraciones.
- Pruebas de integración (marcador `integration`) crean una base vacía, aplican todas las migraciones, verifican las convenciones del ADR-0029 y revierten hasta la base; el CI las ejecuta contra un servicio PostGIS.

## Alternativas consideradas

| Alternativa                                     | Ventajas                                   | Desventajas                                                                                     | Motivo de descarte                            |
| ----------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Archivos SQL numerados con un ejecutor propio   | Sin dependencias                           | Reimplementa control de versiones, bloqueo y reversión                                          | Mantener herramientas propias no aporta valor |
| Flyway                                          | Muy maduro, SQL puro                       | Requiere Java o Docker en cada entorno; funciones útiles solo en la edición comercial           | Agrega un ecosistema ajeno al proyecto        |
| Sqitch                                          | Modelo de dependencias explícito, SQL puro | Requiere Perl; poca adopción en el ecosistema Python                                            | Instalación compleja en Windows y CI          |
| dbmate                                          | Binario simple, SQL puro                   | Binario externo a uv; sin integración con Python para pruebas                                   | Peor integración con las pruebas y la API     |
| Alembic con `autogenerate` y modelos SQLAlchemy | Detecta diferencias automáticamente        | No representa bien PostGIS, triggers, `CHECK` ni varios esquemas; duplica el esquema en modelos | El esquema se define mejor en SQL             |

## Consecuencias

### Positivas

- La base registra su versión (`alembic_version`) y se crea desde cero con un solo comando.
- El SQL se revisa como SQL en cada PR, sin traducciones de un ORM.
- La API podrá usar SQLAlchemy, que ya es dependencia de Alembic, sin herramientas adicionales.

### Negativas y riesgos

- Sin `autogenerate`, los cambios del esquema se escriben a mano; las pruebas de integración son la red de seguridad.
- Alembic y SQLAlchemy pasan a ser dependencias del paquete.

## Verificación

- `uv run --env-file .env alembic upgrade head` crea el esquema en una base vacía.
- Las pruebas `integration` aplican y revierten todas las migraciones y verifican índices, auditoría y restricciones.
- El trabajo de CI «Pruebas de integración» las ejecuta contra PostGIS 17-3.5.

## Referencias

- [Alembic](https://alembic.sqlalchemy.org/).
- [PostgreSQL — Transactional DDL](https://wiki.postgresql.org/wiki/Transactional_DDL_in_PostgreSQL:_A_Competitive_Analysis).
- [Revisión del esquema canónico](../canonical-schema-review.md).
