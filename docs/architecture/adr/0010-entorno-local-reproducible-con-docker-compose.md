# ADR-0010: Usar Docker Compose para un entorno local reproducible

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-08-22 |
| Decisores   | @Czar272   |
| Tickets     | RGT-27     |
| Reemplaza a | —          |

## Contexto

El sistema depende de servicios de infraestructura (PostgreSQL con PostGIS y, más adelante, OpenTripPlanner). Instalarlos manualmente en cada equipo produce diferencias de versión, configuraciones divergentes y errores difíciles de reproducir.

## Decisión

Los servicios de infraestructura se definen en **`compose.yaml`** y se ejecutan con **Docker Compose**.

- Las imágenes se fijan a una versión explícita; la base de datos usa `postgis/postgis:17-3.5`.
- Cada servicio declara un _healthcheck_.
- Los datos persistentes viven en volúmenes con nombre.
- Las credenciales y puertos provienen de `.env` ([ADR-0009](0009-configuracion-mediante-variables-de-entorno.md)).

## Alternativas consideradas

| Alternativa                           | Ventajas                 | Desventajas                                 | Motivo de descarte            |
| ------------------------------------- | ------------------------ | ------------------------------------------- | ----------------------------- |
| Instalación nativa                    | Sin capa de contenedores | Versiones distintas entre equipos           | No reproducible               |
| Base de datos administrada en la nube | Sin operación local      | Costo y dependencia de red para desarrollar | Innecesario en esta etapa     |
| Kubernetes local                      | Cercano a producción     | Complejidad desproporcionada                | Sobredimensionado para el MVP |

## Consecuencias

### Positivas

- Cualquier persona levanta el entorno con `docker compose up -d`.
- La misma definición sirve como base para la integración continua.

### Negativas y riesgos

- Requiere Docker instalado y recursos de memoria suficientes.
- Actualizar versiones de imágenes debe hacerse de forma explícita y probada.

## Verificación

- `compose.yaml` define el servicio `db` con imagen fijada, healthcheck y volumen `rutagt_postgres_data`.
- `docker compose ps` reporta el servicio `db` en estado `healthy`.

## Referencias

- `README.md`, sección «Base de datos».
