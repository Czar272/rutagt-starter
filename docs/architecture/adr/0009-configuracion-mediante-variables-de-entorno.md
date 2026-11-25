# ADR-0009: Configurar el sistema mediante variables de entorno

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-08-18 |
| Decisores   | @Czar272   |
| Tickets     | RGT-26     |
| Reemplaza a | —          |

## Contexto

RutaGT se ejecutará en distintos equipos y entornos (desarrollo, integración continua y, más adelante, producción). Algunos valores varían entre entornos (rutas de datos, conexión a la base) y otros son secretos (contraseñas). Incluirlos en el código o en archivos versionados impediría desplegar en otros entornos y expondría credenciales en un repositorio público.

## Decisión

La configuración que varía entre entornos se lee de **variables de entorno con el prefijo `RUTAGT_`**, siguiendo el principio de configuración del _Twelve-Factor App_.

- `.env.example` se versiona como plantilla documentada, sin secretos reales.
- `.env` es local y está excluido de Git.
- Docker Compose consume `.env`; los servicios futuros también.
- Cada variable tiene un valor por defecto seguro para desarrollo cuando es posible.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Archivos de configuración versionados por entorno | Visibles | Riesgo de versionar secretos | Inseguro en un repositorio público |
| Valores fijos en el código | Simple | Imposible cambiar de entorno sin modificar código | No portable |

## Consecuencias

### Positivas

- Los secretos nunca se versionan.
- El mismo artefacto se ejecuta en cualquier entorno cambiando solo variables.

### Negativas y riesgos

- El recolector actual no carga `.env` automáticamente; solo lee el entorno del proceso. La carga uniforme se define junto con los patrones del pipeline (RGT-122).

## Verificación

- `.env.example` documenta todas las variables `RUTAGT_*`.
- `.gitignore` excluye `.env` y `.env.*`, excepto `.env.example`.
- `compose.yaml` no contiene credenciales literales.

## Referencias

- [The Twelve-Factor App — III. Config](https://12factor.net/config).
- `README.md`, sección «Configuración local».
