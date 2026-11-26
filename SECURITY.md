# Política de seguridad

## Versiones con soporte

RutaGT está en desarrollo inicial. Solo la rama `main` recibe correcciones de seguridad hasta que se publique la primera versión estable.

| Versión         | Soporte |
| --------------- | ------- |
| `main`          | Sí      |
| Versiones `0.x` | No      |

## Cómo reportar una vulnerabilidad

**No abras un issue público** para reportar una vulnerabilidad.

Repórtala de forma privada desde la pestaña [**Security → Report a vulnerability**](https://github.com/Czar272/rutagt-starter/security/advisories/new) de este repositorio. Incluye, en lo posible:

- descripción del problema y su impacto;
- pasos para reproducirlo o prueba de concepto;
- versión o commit afectado;
- cualquier mitigación conocida.

## Qué esperar

| Etapa                                | Plazo objetivo                                            |
| ------------------------------------ | --------------------------------------------------------- |
| Confirmación de recepción            | 3 días hábiles                                            |
| Evaluación inicial y severidad       | 10 días hábiles                                           |
| Corrección de severidad crítica      | 7 días                                                    |
| Corrección de severidad alta         | 30 días                                                   |
| Corrección de severidad media o baja | Siguiente versión planificada                             |
| Divulgación pública                  | Tras publicar la corrección, coordinada con quien reportó |

Se reconocerá públicamente a quien reporte, salvo que prefiera permanecer en el anonimato.

## Alcance

Incluido: el código de este repositorio, sus flujos de CI y la configuración que se publica en él.

Fuera del alcance: los servicios de terceros (portales de datos, ArcGIS, OpenStreetMap) y los datos publicados por instituciones, que deben reportarse a sus responsables.

## Prácticas de seguridad del proyecto

Las medidas de seguridad del proyecto están descritas en [`docs/architecture/security.md`](docs/architecture/security.md).
