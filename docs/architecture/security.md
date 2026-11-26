# Seguridad

| Campo   | Valor                                           |
| ------- | ----------------------------------------------- |
| Versión | 1.0                                             |
| Fecha   | 2026-11-25                                      |
| Ticket  | RGT-113                                         |
| ADR     | [ADR-0028](adr/0028-linea-base-de-seguridad.md) |

Este documento define la línea base de seguridad de RutaGT: qué se protege, frente a qué amenazas y con qué controles. Las medidas marcadas como _activo_ ya funcionan en el repositorio; las demás se implementan con el componente correspondiente. La política para reportar vulnerabilidades está en [`SECURITY.md`](../../SECURITY.md).

## 1. Referencias

- **OWASP ASVS 4.0.3, nivel 1** como requisito mínimo para la API y la PWA.
- **OWASP Top 10** como lista de verificación en la revisión de pull requests.
- **Supply-chain Levels for Software Artifacts (SLSA)** como guía para la cadena de suministro.

## 2. Activos y amenazas

| Activo                                | Amenaza principal                                                                      | Impacto | Controles                                                                                                                                                         |
| ------------------------------------- | -------------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Integridad de los datos de transporte | Datos manipulados o fuentes comprometidas que generan itinerarios erróneos o inseguros | Alto    | Procedencia con SHA-256, capas inmutables ([ADR-0004](adr/0004-capas-de-datos-inmutables-con-procedencia.md)), validaciones, revisión de cambios por pull request |
| Privacidad de las consultas           | Registro de ubicaciones de origen y destino                                            | Alto    | Sin ubicaciones exactas en telemetría ([observabilidad](observability.md#7-privacidad-y-retención)), política RGT-112                                             |
| Disponibilidad de la API              | Abuso o denegación de servicio                                                         | Medio   | Límites de tasa, tiempos de espera, tamaño máximo de petición                                                                                                     |
| Cadena de suministro                  | Dependencia o acción de CI comprometida                                                | Alto    | Lockfile con hashes, auditoría de vulnerabilidades, acciones fijadas por SHA, Dependabot                                                                          |
| Secretos                              | Credenciales expuestas en el repositorio                                               | Alto    | `.env` fuera de Git, secret scanning con push protection, hook de claves privadas                                                                                 |
| Pipeline de CI                        | Ejecución de código no revisado con permisos amplios                                   | Medio   | `permissions: contents: read`, `main` protegida, verificaciones obligatorias                                                                                      |

## 3. Secretos

| Control                                                                                                                                                  | Estado                 |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| Configuración sensible solo en variables de entorno y `.env` local excluido de Git ([ADR-0009](adr/0009-configuracion-mediante-variables-de-entorno.md)) | Activo                 |
| `.env.example` sin valores reales                                                                                                                        | Activo                 |
| Hook `detect-private-key` en pre-commit                                                                                                                  | Activo                 |
| GitHub secret scanning con **push protection** (bloquea el push de un secreto reconocido)                                                                | Activo                 |
| Secretos de CI y despliegue en _GitHub Actions secrets_ por entorno, nunca en el código                                                                  | Al crear el despliegue |
| Gestor de secretos del proveedor en producción y rotación ante cualquier exposición                                                                      | Antes de producción    |

Ante una exposición: revocar y rotar el secreto inmediatamente; eliminarlo del historial no basta.

## 4. Dependencias y cadena de suministro

| Control                                                                                                                                    | Estado    |
| ------------------------------------------------------------------------------------------------------------------------------------------ | --------- |
| Dependencias fijadas en `uv.lock`; el CI instala con `UV_LOCKED=1`                                                                         | Activo    |
| **Auditoría de vulnerabilidades** con `pip-audit` sobre las dependencias exportadas con hashes, en cada push, pull request y semanalmente  | Activo    |
| **Dependabot**: alertas de vulnerabilidades, pull requests de seguridad automáticos y actualizaciones semanales de dependencias y acciones | Activo    |
| GitHub Actions fijadas por SHA de commit y con permisos mínimos ([ADR-0021](adr/0021-integracion-continua-con-github-actions.md))          | Activo    |
| Hooks de pre-commit con versión fijada                                                                                                     | Activo    |
| Imágenes de contenedor con versión explícita (`postgis/postgis:17-3.5`); fijación por digest en producción                                 | Parcial   |
| PWA: lockfile de npm versionado y `npm audit` en CI                                                                                        | Sprint 11 |
| Revisión de licencias de dependencias                                                                                                      | RGT-111   |

## 5. Análisis de código

| Control                                                                                             | Estado |
| --------------------------------------------------------------------------------------------------- | ------ |
| Reglas de seguridad de Ruff (`S`, basadas en Bandit) en pre-commit y CI                             | Activo |
| **CodeQL** (configuración gestionada por GitHub, consultas extendidas) para Python y GitHub Actions | Activo |
| Tipado estricto con mypy                                                                            | Activo |
| Revisión de cada cambio mediante pull request con verificaciones obligatorias                       | Activo |

## 6. API (Sprint 10)

| Aspecto               | Requisito                                                                                                                                                                                                      |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Transporte            | Solo HTTPS; HSTS con `max-age` ≥ 1 año                                                                                                                                                                         |
| CORS                  | Lista explícita de orígenes permitidos (dominios de la PWA); nunca `*`. Métodos `GET` y `OPTIONS`; sin credenciales                                                                                            |
| Límites de tasa       | Por IP: 60 peticiones/min en `/plan` y 300/min en el resto; respuesta `429` con `Retry-After`. Aplicados en el borde (proxy o CDN) y como respaldo en la aplicación                                            |
| Validación de entrada | Modelos Pydantic estrictos: coordenadas dentro del área de cobertura, longitud máxima de textos, enumeraciones cerradas; se rechaza lo desconocido                                                             |
| Recursos              | Tamaño máximo de petición, tiempos de espera hacia PostGIS y OpenTripPlanner, paginación con límite máximo                                                                                                     |
| Errores               | Mensajes genéricos al cliente con `request_id`; sin trazas ni detalles internos                                                                                                                                |
| Encabezados           | `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy` restrictiva en la PWA, `Permissions-Policy` que solo permite geolocalización al propio origen |
| Autenticación         | Los endpoints públicos de consulta no requieren autenticación ni recolectan datos personales. Cualquier endpoint administrativo futuro exigirá autenticación fuerte y autorización por rol                     |

## 7. Base de datos

- Roles de mínimo privilegio: `rutagt_pipeline` (escritura de datos), `rutagt_api` (solo lectura) y un rol de migraciones; las aplicaciones nunca usan el superusuario.
- Conexiones cifradas (TLS) fuera del entorno local.
- La base no se expone a Internet; solo la API y el pipeline acceden a ella.
- Consultas siempre parametrizadas mediante SQLAlchemy; nunca concatenación de texto.
- Respaldos y recuperación según RGT-108.

## 8. Actualizaciones y parches

Plazos para vulnerabilidades conocidas en dependencias que ya tienen una versión corregida. Los reportes de vulnerabilidades en el código propio siguen los plazos de [`SECURITY.md`](../../SECURITY.md).

| Severidad de la vulnerabilidad | Plazo para corregir o mitigar       |
| ------------------------------ | ----------------------------------- |
| Crítica                        | 48 horas                            |
| Alta                           | 7 días                              |
| Media                          | 30 días                             |
| Baja                           | Siguiente actualización planificada |

- Las propuestas de Dependabot se revisan cada semana.
- Se revisa trimestralmente el fin de soporte de Python, PostgreSQL/PostGIS, OpenTripPlanner y Node.
- Un hallazgo de la auditoría de dependencias o de CodeQL bloquea la integración hasta corregirse o documentar una excepción justificada con fecha de revisión.

## 9. Respuesta a vulnerabilidades

Los reportes se reciben de forma privada según [`SECURITY.md`](../../SECURITY.md), se evalúan con CVSS, se corrigen en un _security advisory_ privado y se divulgan de forma coordinada al publicar la corrección.
