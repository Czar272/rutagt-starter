# Fixture de los normalizers

Extractos de las cuatro capas GIS de la Municipalidad de Guatemala (Dirección de Movilidad Urbana / DIGM), publicadas en su portal de datos abiertos para uso público y reutilización con atribución. Los registros se copian sin cambios desde el snapshot `20261126T181403Z`; el archivo solo se reescribe en el formato JSON determinista de `rutagt.core.io.write_json`.

| Archivo                                  | Registros (`FID`)                                                  | Casos que cubre                                                                                                                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `raw/.../transmetro_stops_2025.geojson`  | 19, 20, 22, 24, 25, 26, 44, 54, 82, 85, 86, 91, 141, 142, 144, 145 | Sentido en el nombre, sentido repetido (Granai, E6), zona discrepante, espacios anómalos, sufijo de líneas, andenes sin trazado                                                           |
| `raw/.../tubus_stops_2025.geojson`       | Ruta 801 completa (49) + 143, 163, 205, 214, 226, 258              | Secuencia de la 801 con su rutero y revisión (RGT-127), número repetido y registro duplicado (B2, B7), sentido en la dirección, zona discrepante, espacio no separable, rutas sin trazado |
| `raw/.../transmetro_routes_2025.geojson` | 6, 7, 9, 12                                                        | Línea 18 en circuito (`MultiLineString`), correcciones ortográficas, variantes con trazado compartido                                                                                     |
| `raw/.../tubus_routes_2025.geojson`      | 1, 5, 7                                                            | Código como texto (rutas 801, 305 y 402)                                                                                                                                                  |

Cada archivo tiene su `.provenance.json` con el snapshot de origen, la fecha de la descarga original (`fetched_at`, que usa el constructor canónico), los `FID` elegidos, el motivo y el SHA-256 que verifica el runner. El mismo fixture alimenta las pruebas del constructor canónico y de la carga a PostGIS.

## Regenerar

Con el recolector ya ejecutado, desde la raíz del repositorio:

```powershell
uv run python tests/fixtures/normalizers/extract_fixture.py            # extractos desde el snapshot vigente
$env:RUTAGT_UPDATE_GOLDEN = "1"; uv run pytest tests/pipeline/normalizers/test_golden.py; Remove-Item Env:RUTAGT_UPDATE_GOLDEN
```

`expected_summary.json` es el resumen esperado de cada lote: registros con sus campos interpretados y problemas con severidad. Revisar su diff antes de confirmarlo: cada cambio debe explicarse por un cambio intencional en un adaptador o en las validaciones.
