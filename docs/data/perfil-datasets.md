# Perfil de los datasets municipales

| Campo    | Valor                                                                    |
| -------- | ------------------------------------------------------------------------ |
| Ticket   | RGT-34                                                                   |
| Snapshot | `20261126T181403Z` ([versionado](versionado-datasets.md))                |
| Datasets | Rutas y paradas de Transmetro y TuBus 2025 (ArcGIS, Municipalidad de Guatemala) |
| Fecha    | 2026-11-26                                                               |

Inventario de campos, nulos, duplicados, códigos y anomalías de las cuatro capas GIS, con sus consecuencias para la normalización (Sprint 6). Complementa el [inventario de cobertura](inventario-cobertura.md).

## 1. Cómo se genera

```powershell
uv run rutagt-profile                        # snapshot vigente (data/raw/LATEST)
uv run rutagt-profile --snapshot <id>        # un snapshot concreto
```

El comando escribe en `data/staging/<snapshot>/profiles/`:

- `profiles.json`: perfil completo por dataset;
- `perfil.md`: el mismo perfil en tablas;
- `profiles.json.provenance.json`: snapshot, SHA-256 de cada entrada, commit del código y checksums de salida ([ADR-0032](../architecture/adr/0032-versionado-de-datasets-con-snapshots-inmutables.md)).

Por cada campo calcula:

- tipos, nulos y vacíos;
- valores distintos y si son únicos;
- valores repetidos más frecuentes;
- rango numérico o de longitud;
- espacios anómalos (al inicio, al final, dobles o no separables);
- codificación dañada.

Por cada capa calcula, además:

- tipos de geometría y extensión;
- puntos fuera de Guatemala;
- geometrías idénticas.

Este documento añade las **comprobaciones entre datasets**, que dependen del dominio y no las hace el comando.

## 2. Resumen

| Dataset              | Registros | Geometría                            | Campos                                                  | Nulos | Fuera de Guatemala | Codificación |
| -------------------- | --------- | ------------------------------------ | ------------------------------------------------------- | ----- | ------------------ | ------------ |
| Rutas Transmetro     | 12        | 11 `LineString`, 1 `MultiLineString` | `FID`, `Nombre`, `Codigoruta`, `Shape__Length`          | 0     | 0                  | Correcta     |
| Estaciones Transmetro | 169      | `Point`                              | `FID`, `Nombre_lug`, `Direccion`, `Zona`, `Codigoruta`  | 0     | 0                  | Correcta     |
| Rutas TuBus          | 8         | `LineString`                         | `FID`, `Codigoruta`, `Shape__Length`                    | 0     | 0                  | Correcta     |
| Paradas TuBus        | 278       | `Point`                              | `FID`, `Nombre_lug`, `Codigoruta`, `Direccion`, `Zona`  | 0     | 0                  | Correcta     |

**Lectura general:** las capas son completas en el sentido técnico: no hay nulos, todas las geometrías caen dentro de la ciudad y el texto está bien codificado en UTF-8. Los problemas son de **modelo y consistencia**:

- códigos con tipos distintos entre capas;
- variantes sin geometría propia;
- el sentido escrito dentro del nombre;
- zonas que contradicen la dirección;
- direcciones sin formato común.

## 3. Hallazgos por dataset

### Rutas Transmetro

| # | Hallazgo | Evidencia | Consecuencia para la normalización |
| --- | --- | --- | --- |
| P1 | `Codigoruta` codifica línea y variante | `1000`, `2000`, …, `12000`, `12001`, `12002`, `18000`–`18002` (línea × 1000 + variante) | Derivar `route` (línea) y `route_pattern` (variante) del código; documentar la regla y validarla con la Municipalidad |
| P2 | Las variantes no tienen trazado propio | La Línea 12 y sus dos «Directo» comparten geometría idéntica; también las dos variantes «Expres» de la Línea 18 | La diferencia entre variantes está en las estaciones que sirven, no en el trazado: un mismo `shape` para varios patrones, con paradas distintas |
| P3 | La Línea 18 es un `MultiLineString` | 4 tramos contiguos (ya medido en el inventario). No van en fila: forman un circuito con un lazo en cada extremo (tramo 0 lazo en A, 1 de A a B, 2 de B a A, 3 lazo en B) | Unir en un `LineString` al normalizar, verificando la continuidad. El adaptador de RGT-38 los une en el orden 0, 1, 3, 2 sin invertir ninguno y lo deja en `tramos_unidos`; confirmar el recorrido con la fuente |
| P4 | `Shape__Length` no son metros reales | Es ≈3,5 % mayor que la longitud geodésica en las 20 rutas de ambos sistemas, lo que es consistente con medir en Web Mercator | No usarlo; calcular la longitud con `rutagt_distance_m` o geografía de PostGIS |
| P5 | Errores ortográficos en `Nombre` | «Extención», «Expres» | Corregir en `route_long_name` normalizado conservando el original en `source_record` |

### Estaciones Transmetro

| # | Hallazgo | Evidencia | Consecuencia para la normalización |
| --- | --- | --- | --- |
| E1 | Un registro por estación **y línea** | 169 registros; 92 comparten coordenadas exactas con otros en 32 grupos | Modelar estaciones (`location_type = 1`) con andenes por línea, sin duplicar el punto |
| E2 | El sentido está escrito en el nombre | 26 registros con «Dirección …» o «Dir. …»; el mismo nombre base aparece hasta a 201 m (Reformita, Las Charcas, Mariscal, Bolívar) | Separar nombre de estación y sentido. Los andenes por sentido son paradas distintas. Hay unos **93 nombres base**, no 109 |
| E3 | `Zona` contradice la dirección | 32 de 169 registros: p. ej. FID 44 tiene `Zona = 3` y dirección «zona 8»; FID 47–49 tienen `Zona = 11` y dirección «zona 12» sobre la Calzada Aguilar Batres, que en parte separa ambas zonas | Ninguno de los dos campos es confiable por sí solo: calcular la zona por ubicación contra los polígonos oficiales de zonas (fuente por incorporar) y marcar la discrepancia en `data_issue` |
| E4 | Direcciones sin formato común | 50 empiezan en minúscula, 26 usan abreviaturas («calz.», «av.»), 20 usan ordinales «6ª» y el resto «6» | Normalizar a un formato canónico para búsqueda; conservar el texto original |
| E5 | Espacios anómalos | 3 nombres y 8 direcciones con espacios dobles, al inicio o al final, o no separables (`U+00A0`) | Limpiar espacios en la capa normalizada |
| E6 | Sentido repetido en dos andenes | FID 144 y 145 se llaman «Granai - Dir. La Merced» en la Línea 7, a unos 40 m, uno sobre el Periférico Norte y otro sobre el Sur; los demás pares de la línea tienen un andén por sentido (lo detectó el adaptador de RGT-36) | Probablemente FID 145 es «Dir. USAC Periférico»; se marca `sentido_duplicado` y se pregunta a la fuente antes de corregir |

### Rutas TuBus

| # | Hallazgo | Evidencia | Consecuencia para la normalización |
| --- | --- | --- | --- |
| T1 | `Codigoruta` es **texto** | `"5"`, `"104"`, … `"802"` | En las paradas es número: convertir ambos a texto antes de unir (ver X1) |
| T2 | `Shape__Length` no son metros | Igual que P4 | Igual que P4 |
| T3 | Sin nombre ni sentido de la ruta | Solo `FID`, `Codigoruta` y longitud | Nombre, sentido y horario provienen de los ruteros oficiales (PDF) |

### Paradas TuBus

| # | Hallazgo | Evidencia | Consecuencia para la normalización |
| --- | --- | --- | --- |
| B1 | Nombres genéricos | 193 de 278 se llaman «Parada NNN» | El nombre visible debe construirse con la dirección o una referencia cercana; el número sirve solo como pista (el spike lo confirmó) |
| B2 | Numeración repetida | «Parada 105» aparece dos veces en la ruta 801 (FID 101 y 102) y una en la 802 | El número de parada no es un identificador; usar `FID` en la procedencia y un identificador propio (`muniguate:stop:…`) |
| B3 | Cada parada pertenece a una sola ruta | Ninguna coordenada se repite entre rutas | Paradas físicas compartidas entre rutas, si existen, deben detectarse por proximidad, no por coordenadas idénticas |
| B4 | Direcciones mixtas | 141 sin «zona» (usan colonia o barrio), 104 con ordinales «10a» y 5 con «10ª», 14 con abreviaturas, 16 terminan en punto; duplicados que solo difieren en el punto final | Normalizar formato; la colonia es útil para búsqueda y debe conservarse |
| B5 | `Zona` contradice la dirección | 6 casos (p. ej. FID 204–206: `Zona = 7` con dirección «zona 3») | Igual que E3 |
| B6 | Espacios anómalos | 3 nombres y 14 direcciones | Igual que E5 |
| B7 | Registro probablemente duplicado | FID 143 y 258 de la ruta 402 tienen el mismo nombre («Parada 190») y la misma dirección, a 6 m; en cambio, los dos «Parada 105» de la ruta 801 están a 519 m y son paradas distintas (lo detectó el adaptador de RGT-37) | Se marca `numero_repetido`; el constructor canónico decide si se fusionan por proximidad, y se pregunta a la fuente |

## 4. Comprobaciones entre datasets

| # | Comprobación | Resultado | Acción |
| --- | --- | --- | --- |
| X1 | Códigos de ruta de paradas frente a rutas | Coinciden los 8 de TuBus y los 12 de Transmetro, pero en TuBus el tipo difiere (texto en rutas, número en paradas) | Unir siempre por el código convertido a texto |
| X2 | Paradas TuBus cerca de estaciones Transmetro | 19 paradas TuBus a 100 m o menos de una estación Transmetro (rutas 104, 801 y 802) | Son candidatas a **transbordo**; validar en campo antes de crear `transfer` |
| X3 | Zonas presentes | Transmetro: 13 zonas entre 1 y 18; TuBus: zonas 1 a 15 | Todas existen en el municipio; las discrepancias de E3 y B5 son de asignación, no de zonas inexistentes |
| X4 | Extensión | Ambas capas dentro de lon −90,572 a −90,441 y lat 14,562 a 14,673 | Sin coordenadas fuera de lugar |

## 5. Preguntas para la fuente

Para incluir en el primer contacto técnico con la Municipalidad:

1. ¿El código de Transmetro sigue la regla línea × 1000 + variante? ¿Qué distingue a las variantes «Directo» y «Expres» además de las estaciones?
2. ¿El campo `Zona` se asignó por la dirección o por la ubicación? ¿Cuál es correcto en los 38 casos que no coinciden?
3. ¿Las estaciones con el mismo nombre separadas hasta 200 m son andenes de distinto sentido?
4. ¿La numeración de paradas TuBus («Parada NNN») tiene un significado operativo?
5. ¿El andén FID 145 de la estación Granai (Periférico Sur) corresponde a la dirección USAC Periférico?
6. ¿Los registros FID 143 y 258 de la ruta 402 («Parada 190») son la misma parada?

## 6. Brechas que el perfil confirma

- **Polígonos oficiales de zonas** para calcular la zona por ubicación (E3, B5): es una fuente nueva por identificar.
- **Secuencia y sentido** siguen sin estar en las capas: dependen de los ruteros (TuBus) y del catálogo de Transmetro, bloqueado para descargas automáticas (inventario de cobertura).
