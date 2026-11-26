# ADR-0034: Validar la geometría de staging con reglas de severidad fija y umbrales calibrados

| Campo       | Valor      |
| ----------- | ---------- |
| Estado      | Aceptado   |
| Fecha       | 2026-11-26 |
| Decisores   | @Czar272   |
| Tickets     | RGT-40     |
| Reemplaza a | —          |

## Contexto

Los adaptadores de RGT-36 a RGT-39 validan la forma de cada registro: punto válido, línea continua, tipos correctos. No comprueban que la geometría tenga sentido para una red de transporte urbano:

- una coordenada con el signo invertido sigue siendo un punto válido;
- un trazado puede saltar kilómetros entre dos vértices;
- una parada puede estar asignada a una ruta que no pasa por ella.

ADR-0033 dejó para este ticket qué validaciones geoespaciales se ejecutan y con qué severidad. Un problema `error` impide pasar el lote a la capa canónica y hace fallar `rutagt-normalize`; `warning` e `info` se cargan en `provenance.data_issue`.

Con el snapshot `20261126T181403Z` se midió el comportamiento real de las cuatro capas:

- distancia de cada parada al trazado de su ruta: mediana de 4 a 5 m, p99 de 18 a 22 m, máximo menor a 40 m;
- salto máximo entre vértices: 652 m;
- trazado más corto: 3,5 km.

## Decisión

### Reglas

| Código                 | Severidad | Regla                                                       |
| ---------------------- | --------- | ----------------------------------------------------------- |
| `fuera_de_guatemala`   | error     | Parada o vértice fuera de los límites de Guatemala          |
| `fuera_de_cobertura`   | warning   | Dentro de Guatemala, pero fuera del Área Metropolitana      |
| `salto_en_trazado`     | warning   | Dos vértices seguidos a más de 1 500 m                      |
| `trazado_corto`        | warning   | Trazado de menos de 500 m                                   |
| `parada_lejos_de_ruta` | warning   | Parada a más de 50 m del trazado de una de sus rutas        |
| `parada_lejos_de_ruta` | error     | Parada a más de 500 m del trazado de una de sus rutas       |
| `ruta_sin_trazado`     | warning   | La fuente de trazados no tiene la ruta que indica la parada |
| `validacion_omitida`   | info      | La fuente de trazados no se normalizó en la misma ejecución |

### Criterios

- **Error solo cuando el dato no puede ser correcto:** una coordenada fuera del país o una parada a medio kilómetro de su ruta. El resto alerta y se revisa con evidencia, sin bloquear la carga.
- **Umbrales calibrados con los datos:** cada umbral deja al menos el doble de margen sobre lo observado en 2025. Están en `normalizers/validations.py`, con el dato observado junto a cada uno, y se revisan si una fuente nueva los supera de forma legítima.
- **Límites como cajas aproximadas** en `rutagt.core.geo`, compartidos con el perfil de datasets. Se reemplazarán por los polígonos oficiales del país y de los municipios cuando se incorporen (perfil, sección de brechas).
- **Cruce de fuentes declarado en el catálogo:** cada capa de paradas indica con `shapes_source` la fuente de trazados de sus rutas, y `load_sources` verifica que exista. Las paradas se unen al trazado por código de variante, si lo hay, y si no por código de ruta.
- **Sin modificar registros:** las validaciones solo agregan `Issue` al lote.

### Ejecución

El runner adapta y valida cada fuente (`validate_batch`) y después cruza paradas con trazados (`validate_stops_against_shapes`). Al final escribe cada lote. Una fuente que falla en cualquiera de los pasos no detiene las demás.

## Alternativas consideradas

| Alternativa                                         | Ventajas                       | Desventajas                                                              | Motivo de descarte                                      |
| --------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------- |
| Validar en PostGIS después de cargar                | Geometría exacta con geografía | El error se detecta después de cargar; requiere base de datos en pruebas | Los errores deben detenerse antes de la capa canónica   |
| Shapely o GeoPandas                                 | Operaciones geométricas ricas  | Dependencia nativa para unos cientos de registros                        | Haversine y distancia a segmento bastan a escala urbana |
| Umbrales por fuente                                 | Ajuste fino                    | Más configuración sin datos que lo justifiquen                           | Un solo conjunto cubre ambas redes con margen           |
| Todo como `warning`                                 | Nunca bloquea                  | Un dato imposible llegaría a la base y a los itinerarios                 | La severidad debe reflejar el impacto                   |
| Emparejar paradas y trazados por convención de `id` | Sin configuración              | Implícito y frágil ante fuentes nuevas                                   | La relación entre fuentes es un dato del catálogo       |

## Consecuencias

### Positivas

- `rutagt-normalize` termina con código 1 si una parada o un trazado es imposible, y el lote no pasa a la capa canónica.
- Cada alerta queda en el lote con su evidencia (distancia, saltos, posiciones) para revisarla.

### Negativas y riesgos

- Las cajas de límites aceptan puntos de países vecinos cerca de la frontera y del Área Metropolitana; el error real es menor que el umbral de distancia a la ruta, que es la validación más estricta.
- La distancia a segmento usa un plano local; el error es despreciable a escala urbana, pero no sirve para rutas interurbanas largas.

## Verificación

- `src/rutagt/pipeline/normalizers/validations.py` y `src/rutagt/core/geo.py`, con pruebas en `tests/pipeline/normalizers/test_validations.py` y `tests/core/test_geo.py`.
- `uv run rutagt-normalize` sobre el snapshot vigente: 4 fuentes sin problemas nuevos.

## Referencias

- [ADR-0033](0033-contrato-de-normalizadores.md), [ADR-0031](0031-escala-de-calidad-y-reglas-de-vigencia.md).
- [Perfil de los datasets municipales](../../data/perfil-datasets.md).
