# ADR-0023: Construir la PWA con React, Vite y MapLibre GL JS

| Campo       | Valor           |
| ----------- | --------------- |
| Estado      | Aceptado        |
| Fecha       | 2026-11-25      |
| Decisores   | @Czar272        |
| Tickets     | RGT-121, RGT-70 |
| Reemplaza a | —               |

## Contexto

[ADR-0016](0016-pwa-como-cliente-principal.md) establece una Progressive Web App como cliente principal del MVP, orientada a teléfonos Android de gama media o baja con conectividad intermitente. La PWA debe mostrar búsqueda de origen y destino, alternativas, detalle paso a paso y un mapa con recorridos y paradas (épica RGT-6), y cumplir el criterio C7 del [alcance del MVP](../../product/alcance-mvp.md): Lighthouse ≥ 90 en rendimiento y accesibilidad en un dispositivo de gama baja.

La PWA consume únicamente la API RutaGT ([ADR-0022](0022-fastapi-para-la-api.md)) y no necesita renderizado en servidor: el contenido depende de la ubicación y la consulta de cada persona.

## Evaluación

### Framework

Escala de 1 (deficiente) a 5 (excelente).

| Criterio                                               |  Peso | React + Vite | SvelteKit | Vue + Vite | Next.js | Angular |
| ------------------------------------------------------ | ----: | :----------: | :-------: | :--------: | :-----: | :-----: |
| Rendimiento y tamaño del bundle en gama baja           |  25 % |      3       |     5     |     4      |    3    |    2    |
| Capacidades PWA (service worker, offline, instalación) |  15 % |      5       |     4     |     5      |    3    |    5    |
| Integración con MapLibre GL JS                         |  15 % |      5       |     4     |     4      |    4    |    3    |
| Ecosistema, talento y valor de portafolio              |  15 % |      5       |     3     |     4      |    5    |    4    |
| Accesibilidad (componentes y herramientas)             |  10 % |      4       |     4     |     3      |    4    |    4    |
| TypeScript y experiencia de desarrollo                 |  10 % |      5       |     4     |     4      |    4    |    4    |
| Sostenibilidad a largo plazo                           |  10 % |      5       |     4     |     4      |    4    |    4    |
| **Puntaje ponderado**                                  | 100 % |   **4.40**   |   4.10    |    4.05    |  3.75   |  3.50   |

Observaciones:

- **React + Vite** ofrece el mayor ecosistema, integración madura con MapLibre (`react-map-gl/maplibre`) y PWA mediante `vite-plugin-pwa` (Workbox). Su desventaja de tamaño se controla con el presupuesto de rendimiento y la carga diferida del mapa.
- **SvelteKit** produce los bundles más pequeños y fue la alternativa más cercana; se descartó por un ecosistema y una disponibilidad de talento menores, relevantes para la continuidad del proyecto.
- **Next.js** está orientado a renderizado en servidor, que el MVP no necesita y que exige operar un servidor Node.
- **Angular** genera bundles más pesados para el perfil de dispositivo objetivo.

### Librería de mapas

Se adopta **MapLibre GL JS**: abierta (licencia BSD), con mapas vectoriales fluidos, sin claves de API ni costos por uso, y compatible con tiles de OpenStreetMap autoalojados. Se descartaron Leaflet (solo tiles ráster, menor fluidez) y Google Maps/Mapbox (costos por uso y términos que limitan datos derivados, contrarios a [ADR-0007](0007-adquirir-datos-solo-por-canales-legitimos.md)).

## Decisión

| Aspecto           | Elección                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Lenguaje          | TypeScript en modo estricto                                                                                                          |
| Framework         | React con Vite; aplicación de una sola página (SPA) estática, sin renderizado en servidor                                            |
| PWA               | `vite-plugin-pwa` (Workbox): manifiesto, instalación y caché de consultas recientes ([ADR-0016](0016-pwa-como-cliente-principal.md)) |
| Mapas             | MapLibre GL JS mediante `react-map-gl/maplibre`, cargado de forma diferida                                                           |
| Mapa base         | Tiles vectoriales de OpenStreetMap; la fuente concreta (autoalojada o servicio abierto) se decide en RGT-75 con atribución ODbL      |
| Cliente de la API | Tipos generados desde el contrato OpenAPI de la API                                                                                  |
| Calidad           | ESLint, Prettier y `tsc --noEmit` en pre-commit y CI                                                                                 |
| Pruebas           | Vitest y Testing Library; pruebas extremo a extremo con Playwright a partir del Sprint 11                                            |
| Despliegue        | Archivos estáticos servidos desde CDN                                                                                                |

### Presupuesto de rendimiento

Medido en la emulación de dispositivo móvil de gama baja de Lighthouse (CPU 4× más lenta, red 4G lenta):

| Métrica                                      | Presupuesto                              |
| -------------------------------------------- | ---------------------------------------- |
| JavaScript inicial (comprimido), sin el mapa | ≤ 170 KB                                 |
| MapLibre y estilos del mapa                  | Carga diferida, fuera del bundle inicial |
| Largest Contentful Paint (LCP)               | ≤ 2.5 s                                  |
| Interaction to Next Paint (INP)              | ≤ 200 ms                                 |
| Cumulative Layout Shift (CLS)                | ≤ 0.1                                    |
| Lighthouse rendimiento y accesibilidad       | ≥ 90                                     |

El presupuesto se verificará en CI cuando exista la PWA (RGT-70, RGT-78).

## Consecuencias

### Positivas

- Ecosistema amplio y estable, con soluciones probadas para mapas, PWA y accesibilidad.
- Despliegue estático de bajo costo, sin servidor de aplicación para el cliente.
- Mapas abiertos sin costos por uso ni dependencia de proveedores comerciales.

### Negativas y riesgos

- React tiene un costo base mayor que Svelte; el presupuesto de rendimiento y la carga diferida son obligatorios para cumplir C7.
- Se incorpora un segundo ecosistema de herramientas (Node/TypeScript) en el repositorio, con su propio lockfile y verificaciones de CI.

## Verificación

- La PWA declara TypeScript estricto, React, Vite, `vite-plugin-pwa` y MapLibre GL JS en su `package.json` con lockfile versionado.
- El CI ejecuta lint, verificación de tipos, pruebas y el presupuesto de rendimiento de la PWA.

## Referencias

- [React](https://react.dev/), [Vite](https://vite.dev/), [vite-plugin-pwa](https://vite-pwa-org.netlify.app/), [MapLibre GL JS](https://maplibre.org/), [react-map-gl](https://visgl.github.io/react-map-gl/).
- [web.dev — Core Web Vitals](https://web.dev/articles/vitals).
