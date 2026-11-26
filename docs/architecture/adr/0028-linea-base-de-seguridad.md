# ADR-0028: Adoptar una línea base de seguridad basada en OWASP ASVS nivel 1 y controles automatizados

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-25 |
| Decisores   | @Czar272   |
| Tickets     | RGT-113    |
| Reemplaza a | —          |

## Contexto

RutaGT es un repositorio público que aspira a ser adoptado por instituciones públicas. Sus riesgos principales son la integridad de los datos de transporte (un dato manipulado puede producir un itinerario inseguro), la privacidad de las consultas de las personas, la cadena de suministro de dependencias y acciones de CI, la exposición de secretos y, cuando exista la API, el abuso del servicio. Hasta ahora existían controles aislados (secret scanning, reglas de seguridad de Ruff, validación del esquema de URL), pero no una política que definiera requisitos, responsables de cada control ni plazos de corrección.

## Decisión

- **Referencia:** OWASP ASVS 4.0.3 nivel 1 como requisito mínimo para la API y la PWA, y OWASP Top 10 como lista de verificación en revisión.
- **Secretos:** solo en variables de entorno; secret scanning con push protection y hook de claves privadas.
- **Cadena de suministro:** lockfile, auditoría `pip-audit` con hashes en cada push, pull request y semanalmente como verificación obligatoria; Dependabot (alertas, actualizaciones de seguridad y de versiones); acciones fijadas por SHA con permisos mínimos.
- **Análisis de código:** CodeQL gestionado por GitHub (Python y Actions, consultas extendidas) y reglas de seguridad de Ruff.
- **API:** HTTPS con HSTS, CORS con lista explícita de orígenes, límites de tasa por IP, validación estricta con Pydantic, límites de recursos, errores genéricos y encabezados de seguridad; sin autenticación para consultas públicas y autenticación fuerte para cualquier endpoint administrativo.
- **Base de datos:** roles de mínimo privilegio, TLS fuera del entorno local, sin exposición a Internet y consultas parametrizadas.
- **Parches:** dependencias vulnerables con corrección disponible en 48 h (crítica), 7 días (alta) y 30 días (media).
- **Divulgación:** reporte privado de vulnerabilidades de GitHub según `SECURITY.md`.

El detalle está en [`docs/architecture/security.md`](../security.md).

## Alternativas consideradas

| Alternativa                                             | Ventajas                    | Desventajas                                                                      | Motivo de descarte                                            |
| ------------------------------------------------------- | --------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| OWASP ASVS nivel 2                                      | Mayor exigencia             | Costo desproporcionado para una API pública de solo lectura sin datos personales | Se revisará si se agregan cuentas o datos sensibles           |
| Herramientas comerciales de análisis (Snyk, SonarCloud) | Paneles y cobertura amplia  | Dependencia externa y posibles costos                                            | GitHub ofrece CodeQL, Dependabot y secret scanning sin costo  |
| Auditoría solo con Dependabot                           | Sin configuración adicional | Las alertas no bloquean la integración                                           | `pip-audit` en CI hace obligatorio corregir antes de integrar |
| Autenticación en todas las consultas                    | Control de acceso fino      | Fricción para las personas usuarias y para terceros                              | Las consultas públicas no manejan datos personales            |

## Consecuencias

### Positivas

- Los controles de cadena de suministro y secretos funcionan desde ahora de forma automática.
- La API se diseñará con requisitos de seguridad conocidos de antemano.
- Existe un canal privado y plazos definidos para reportar y corregir vulnerabilidades.

### Negativas y riesgos

- Una vulnerabilidad publicada en una dependencia puede bloquear temporalmente la integración de pull requests no relacionados.
- Los límites de tasa iniciales son estimaciones que deben calibrarse con el uso real.

## Verificación

- El flujo CI incluye el trabajo «Auditoría de dependencias», obligatorio en el ruleset de `main`, y se ejecuta semanalmente.
- El repositorio tiene activos secret scanning con push protection, alertas y actualizaciones de seguridad de Dependabot, reporte privado de vulnerabilidades y CodeQL.
- `SECURITY.md` existe en la raíz del repositorio.

## Referencias

- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), [OWASP Top 10](https://owasp.org/www-project-top-ten/).
- [pip-audit](https://github.com/pypa/pip-audit), [CodeQL](https://codeql.github.com/), [Dependabot](https://docs.github.com/code-security/dependabot).
- [`docs/architecture/security.md`](../security.md).
