# ADR-0016: Usar una PWA como cliente principal del MVP

| Campo       | Valor           |
| ----------- | --------------- |
| Estado      | Propuesto       |
| Fecha       | 2026-11-25      |
| Decisores   | @Czar272        |
| Tickets     | RGT-70, RGT-121 |
| Reemplaza a | —               |

## Contexto

Las personas usuarias de transporte público en Guatemala acceden principalmente desde teléfonos Android de gama media o baja, con almacenamiento limitado y conectividad variable. Publicar aplicaciones nativas para Android e iOS duplica el desarrollo y exige instalación desde tiendas.

## Decisión propuesta

El cliente principal del MVP es una **Progressive Web App (PWA)**:

- Instalable desde el navegador, sin tiendas de aplicaciones.
- Con un **presupuesto de rendimiento** explícito para dispositivos de gama baja.
- Con funcionamiento degradado sin conexión para consultas recientes.
- Accesible según WCAG 2.1 nivel AA como objetivo.

Una aplicación nativa solo se considerará cuando funciones como GPS en segundo plano o notificaciones lo justifiquen. El framework y la librería de mapas se decidirán en RGT-121 con su propio ADR.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Estado |
| --- | --- | --- | --- |
| Apps nativas Android/iOS | Acceso completo al dispositivo | Doble desarrollo, instalación obligatoria | Pospuesta |
| Multiplataforma (Flutter, React Native) | Un código para ambas tiendas | Sigue requiriendo tiendas e instalación | Pospuesta |
| Sitio web sin capacidades PWA | Más simple | Sin instalación ni modo sin conexión | Insuficiente |

## Consecuencias esperadas

### Positivas

- Un solo cliente para todas las plataformas, accesible con un enlace.
- Menor barrera de adopción para usuarios y para presentaciones institucionales.

### Negativas y riesgos

- Capacidades limitadas en iOS (notificaciones y segundo plano).

## Verificación

- Auditoría Lighthouse con puntajes mínimos de rendimiento, accesibilidad y PWA (RGT-78).

## Referencias

- `docs/data/plan-producto-y-datos.md`, sección 9.
