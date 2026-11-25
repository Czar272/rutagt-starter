# Alcance del MVP de RutaGT

| Campo         | Valor                                       |
| ------------- | ------------------------------------------- |
| Versión       | 1.1                                         |
| Fecha         | 2026-11-25                                  |
| Responsable   | @Czar272                                    |
| Ticket        | RGT-117                                     |
| Estado        | Vigente                                     |
| Documentos relacionados | [Plan de producto y datos](../data/plan-producto-y-datos.md), [ADR](../architecture/adr/README.md) |

Este documento define qué entrega el producto mínimo viable (MVP) de RutaGT, para quién, qué queda fuera y cómo se medirá su éxito. Todo ticket del backlog debe poder justificarse contra este alcance; un cambio de alcance se registra actualizando este documento mediante pull request.

## 1. Problema

La información del transporte público del Área Metropolitana de Guatemala está fragmentada entre operadores, municipalidades y documentos no estructurados (capas GIS sin secuencia, PDF, imágenes, redes sociales). No existe una fuente pública, abierta y verificable que indique cómo combinar sistemas para ir de un punto a otro. Las personas dependen de conocimiento previo o de preguntar, y las aplicaciones comerciales existentes no muestran el origen ni la confiabilidad de sus datos.

## 2. Usuarios objetivo

| Usuario | Necesidad principal |
| --- | --- |
| Persona usuaria habitual de transporte público | Encontrar alternativas a su ruta diaria o resolver viajes nuevos |
| Persona que no conoce el sistema (estudiante, visitante, recién llegado) | Saber qué bus tomar, dónde abordarlo y dónde bajarse |
| Persona con movilidad reducida | Identificar opciones accesibles y minimizar caminatas |
| Institución pública u operador (usuario secundario) | Ver cómo sus datos se convierten en información útil y verificable |

Dispositivos: teléfonos **Android e iPhone** con un navegador actual. El diseño toma como referencia de rendimiento los teléfonos Android de gama media o baja, con datos móviles limitados e intermitentes, para que la aplicación funcione bien en cualquier dispositivo ([ADR-0016](../architecture/adr/0016-pwa-como-cliente-principal.md)).

## 3. Propuesta de valor

> Indica dónde estás y a dónde quieres llegar, y RutaGT te dice qué transporte público usar, dónde abordarlo, dónde bajarte y cuánto puedes confiar en esa recomendación.

Lo que diferencia a RutaGT:

1. **Recomendaciones honestas**: los tiempos estimados se muestran como rangos, nunca como horas exactas ficticias, y el ranking prefiere las opciones basadas en datos más confiables ([ADR-0024](../architecture/adr/0024-confianza-interna-y-estimaciones-como-rangos.md)).
2. **Datos abiertos y legítimos**: construido sobre fuentes oficiales y estándares abiertos (GTFS), reutilizable por instituciones ([ADR-0003](../architecture/adr/0003-gtfs-schedule-como-contrato-de-intercambio.md), [ADR-0007](../architecture/adr/0007-adquirir-datos-solo-por-canales-legitimos.md)).
3. **Ligero y accesible**: funciona en dispositivos modestos y conexiones inestables.

## 4. Cobertura del MVP

| Dimensión | Incluido |
| --- | --- |
| Territorio | Ciudad de Guatemala y el corredor piloto **Metrocentro (Villa Nueva) ↔ Universidad del Valle de Guatemala** |
| Sistemas | **Transmetro** y **TuBus** completos según datos oficiales; los sistemas adicionales que exija el corredor piloto (por ejemplo TransMIO o Transurbano), en la medida en que se obtengan sus datos |
| Modos | Transporte público por autobús y caminata |
| Calendario | Días laborales, sábados y domingos/feriados según ventanas de servicio publicadas |
| Idioma | Español |

## 5. Funcionalidades incluidas

| # | Funcionalidad | Épica |
| --- | --- | --- |
| F1 | Búsqueda de origen y destino por texto, ubicación actual o punto en el mapa | RGT-6 |
| F2 | Planificación de itinerarios con alternativas ordenadas por el ranking RutaGT | RGT-4 |
| F3 | Detalle paso a paso: caminata, parada y lado de la vía, ruta y sentido, parada de descenso, transbordos | RGT-6 |
| F4 | Intervalos de espera y tiempos como rangos cuando no hay horario oficial | RGT-4 |
| F5 | Sección «Acerca de los datos» con fuentes, atribución y fecha de actualización | RGT-6 |
| F6 | Costo estimado y medio de pago por tramo cuando la tarifa es conocida | RGT-2 |
| F7 | Mapa con el recorrido y las paradas del itinerario | RGT-6 |
| F8 | Consulta de paradas cercanas y de rutas con su recorrido | RGT-5 |
| F9 | API pública documentada (OpenAPI) con las capacidades anteriores | RGT-5 |
| F10 | Feed GTFS Schedule de Transmetro y TuBus generado de forma reproducible | RGT-3 |
| F11 | Funcionamiento degradado sin conexión para consultas recientes | RGT-6 |

## 6. Fuera del alcance del MVP

| Excluido | Motivo | Etapa prevista |
| --- | --- | --- |
| Información en tiempo real (posición de buses, ETA por viaje) | Requiere convenios AVL con operadores | Épica RGT-9 |
| Aplicaciones nativas Android/iOS | La PWA cubre el MVP | Posterior al MVP |
| Cobertura metropolitana completa y extraurbanos | Se incorpora por corredores | Épica RGT-8 |
| Reportes comunitarios | Requiere moderación y reputación | Épica RGT-8 |
| Panel administrativo para operadores | Requiere acuerdos institucionales | Épica RGT-8 |
| Cuentas de usuario, viajes guardados en servidor y notificaciones | No son necesarios para validar la propuesta de valor | Posterior al MVP |
| Pago o recarga de tarjetas | Fuera del propósito de planificación | No previsto |
| Otros idiomas | — | Posterior al MVP |

## 7. Supuestos

1. Las capas oficiales de la Municipalidad de Guatemala siguen publicadas en el portal de datos abiertos.
2. Las secuencias de paradas por sentido pueden reconstruirse a partir de ruteros oficiales, solicitudes de información y validación de campo.
3. Las frecuencias publicadas o observadas son suficientes para estimar esperas como rangos.
4. OpenTripPlanner produce itinerarios adecuados con el GTFS de RutaGT ([ADR-0014](../architecture/adr/0014-opentripplanner-como-motor-de-planificacion.md), propuesto).
5. Se obtendrá al menos un mecanismo de datos para cada sistema del corredor piloto.

## 8. Restricciones

- Solo se usan datos obtenidos por canales legítimos ([ADR-0007](../architecture/adr/0007-adquirir-datos-solo-por-canales-legitimos.md)).
- Costo de infraestructura bajo, compatible con un proyecto en etapa inicial.
- Atribución y cumplimiento de licencias de las fuentes (OpenStreetMap: ODbL).
- Desarrollo por un equipo reducido con sprints semanales ([ADR-0012](../architecture/adr/0012-gestion-con-scrum-semanal-en-jira.md)).

## 9. Riesgos principales

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Las instituciones no entregan secuencias, horarios o licencias | Alto | Ruteros oficiales, validación de campo y spike de la ruta 801 para dimensionar los datos faltantes |
| La licencia de los datos municipales es imprecisa | Alto | Confirmación escrita antes de redistribuir datos derivados (RGT-111) |
| Rutas que cambian sin aviso | Medio | Recolección periódica, comparación de checksums y caducidad de datos |
| Itinerarios irreales o inseguros | Alto | Tiempos mínimos de transbordo, rangos P90 y suite de rutas doradas (RGT-62) |
| Rendimiento insuficiente en teléfonos de gama baja | Medio | Presupuesto de rendimiento y pruebas en dispositivos reales (RGT-78) |

## 10. Criterios de éxito

El MVP se considera logrado cuando se cumplen todos estos criterios:

| # | Criterio | Meta | Verificación |
| --- | --- | --- | --- |
| C1 | Paradas vigentes de Transmetro y TuBus verificadas en ubicación y sentido | ≥ 95 % | Reporte de calidad de datos |
| C2 | Feed GTFS válido | 0 errores en el validador oficial | RGT-53 |
| C3 | Viajes de prueba sin error grave de dirección, sentido o parada | 20 de 20 en la suite de rutas doradas | RGT-62 |
| C4 | Corredor Metrocentro ↔ UVG validado en ambos sentidos | Itinerario verificado en campo | RGT-83, RGT-84 |
| C5 | Tiempos estimados presentados como rangos y respuestas de la API con confianza y procedencia | 100 % | Pruebas de contrato de la API y de la PWA |
| C6 | Tiempo de respuesta de planificación | p95 < 3 s en el entorno de referencia | Pruebas de rendimiento |
| C7 | PWA en dispositivo de gama baja y en Safari para iOS | Lighthouse ≥ 90 en rendimiento y accesibilidad; flujo principal verificado en iPhone | RGT-78 |
| C8 | Prueba con usuarios piloto | Al menos 10 personas completan un viaje usando RutaGT | RGT-86 |

Las métricas de producto posteriores al lanzamiento se definen en RGT-114.

## 11. Hitos

| Hito | Sprints | Resultado verificable |
| --- | --- | --- |
| H1 — Ingeniería base | 1–2 | Repositorio reproducible, CI obligatorio, decisiones registradas (cumplido) |
| H2 — Arquitectura y datos base | 3–5 | Arquitectura declarada, spike de la ruta 801, esquema migrado y gobierno de datos |
| H3 — Red estática | 6–8 | Datos normalizados, secuencias y primer feed GTFS válido |
| H4 — Planificación | 9–10 | OpenTripPlanner, ranking RutaGT y API MVP |
| H5 — MVP | 11–12 | PWA y corredor piloto validado en campo; criterios C1–C8 cumplidos |

## Historial de cambios

| Versión | Fecha | Cambio |
| --- | --- | --- |
| 1.0 | 2026-11-25 | Versión inicial (RGT-117) |
| 1.1 | 2026-11-25 | Se incluye iPhone en los dispositivos objetivo; la confianza de los datos pasa a uso interno y las estimaciones se muestran como rangos ([ADR-0024](../architecture/adr/0024-confianza-interna-y-estimaciones-como-rangos.md)) |
