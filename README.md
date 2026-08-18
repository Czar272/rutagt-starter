# RutaGT Starter

Base inicial para organizar un planificador multimodal de transporte público en el área metropolitana de Guatemala.

## Estado actual

El proyecto ya cuenta con un recolector reproducible para fuentes públicas. La primera ejecución verificada descargó 169 paradas de Transmetro 2025 desde la Municipalidad de Guatemala y generó su archivo de procedencia y el manifiesto de ejecución.

El recolector también está configurado para consultar:

- Paradas y geometrías de rutas de Transmetro y TuBus.
- Catálogos oficiales de Transmetro y de las rutas 105 y 801 de TuBus.
- El catálogo de datos abiertos de la Dirección General de Transportes.
- Variables y descargas meteorológicas recientes de INSIVUMEH.

Estas fuentes son una base cartográfica y documental; todavía no bastan para calcular un viaje completo. Faltan, entre otros datos, secuencias confiables por sentido, calendarios, frecuencias, tarifas estructuradas, transbordos y telemetría.

## Estructura del proyecto

- `config/sources.json`: catálogo versionado de fuentes y rutas de salida.
- `pipeline/collectors/collect.py`: recolector de servicios ArcGIS y enlaces publicados en páginas HTML.
- `pipeline/normalizers/`: espacio para transformaciones posteriores sin modificar los datos originales.
- `pipeline/validators/`: espacio para validaciones adicionales de calidad.
- `pipeline/exporters/`: espacio para exportar datos derivados, incluido GTFS.
- `database/schema/canonical.sql`: esquema canónico inicial para PostgreSQL 16 + PostGIS 3.
- `data/raw/`: datos originales recolectados y sus archivos de procedencia; está excluida de Git.
- `data/staging/`: datos en preparación.
- `data/normalized/`: datos depurados y normalizados.
- `data/gtfs/`: feeds GTFS de trabajo.
- `data/published/`: artefactos listos para publicación.
- `docs/data/plan-producto-y-datos.md`: alcance, datos, fuentes, módulos, arquitectura y fases.
- `docs/institutions/solicitudes-informacion.md`: plantillas de solicitudes a municipalidades, DGT y operadores.
- `tests/collectors/test_collect.py`: pruebas unitarias del recolector.

## Requisitos

- Python 3.10 o posterior.
- Conexión a Internet para recolectar fuentes.
- PostgreSQL con PostGIS para instalar el esquema, opcional en esta etapa.

El recolector utiliza únicamente la biblioteca estándar de Python.

## Uso rápido

Ejecutar desde la raíz del proyecto:

```powershell
python pipeline/collectors/collect.py list
python pipeline/collectors/collect.py fetch --all --output data/raw
python -m unittest discover -s tests -v
```

También se puede descargar una sola fuente:

```powershell
python pipeline/collectors/collect.py fetch `
  --source muniguate_transmetro_stops_2025 `
  --output data/raw
```

La configuración se resuelve por defecto desde `config/sources.json` y la salida desde `data/raw/`, incluso si el comando se ejecuta desde otra carpeta. También se puede cambiar la carpeta de datos con la variable `RUTAGT_DATA_DIR`.

Cada descarga crea:

- El archivo original normalizado como GeoJSON o JSON, según la fuente.
- Un archivo `.provenance.json` con URL final, fecha UTC, checksum SHA-256, conteos, campos, licencia declarada y alertas de validación.
- `data/raw/run_manifest.json`, con las fuentes exitosas y fallidas de la ejecución.

Una ejecución parcial no borra descargas anteriores. Si una fuente falla, el manifiesto registra el error y el proceso continúa con las demás fuentes.

## Rutas de datos configuradas

Las rutas son relativas al directorio indicado por `--output`:

```text
muniguate/transmetro_stops_2025.geojson
muniguate/tubus_stops_2025.geojson
muniguate/transmetro_routes_2025.geojson
muniguate/tubus_routes_2025.geojson
muniguate/transmetro_catalog_links.json
dgt/open_data_catalog_links.json
insivumeh/weather_catalog_links.json
```

Las fuentes de catálogos de TuBus se guardan en:

```text
muniguate/tubus_route_105_links.json
muniguate/tubus_route_801_links.json
```

## Flujo recomendado

1. Recolectar las capas oficiales públicas sin modificarlas.
2. Conseguir secuencias, calendarios, frecuencias, tarifas y licencias mediante las solicitudes preparadas.
3. Crear una capa de depuración con reglas y revisiones humanas; no sobrescribir el origen.
4. Publicar un primer feed GTFS de Transmetro y TuBus.
5. Probar un corredor de extremo a extremo, por ejemplo Metrocentro/Villa Nueva–UVG.
6. Añadir Transurbano, TransMIO, Express/municipales y extraurbanos mediante acuerdos y entregas verificables.
7. Incorporar AVL/GTFS-Realtime y predicción de llegada después de estabilizar la red estática.

## Decisiones importantes

- La unidad de ruteo no es solo la línea: es `ruta + variante + sentido + calendario`.
- Las fuentes, licencias y vigencias son datos de primera clase.
- Un horario publicado y una observación real nunca se mezclan sin indicar su origen.
- No se debe extraer una aplicación privada por ingeniería inversa ni publicar datos sin permiso.
- El costo de ruta debe permitir preferencias: tiempo, menos transbordos, menos caminata, menor costo y accesibilidad.

## Próximo hito sugerido

Completar un piloto estático validado para Transmetro y TuBus, capaz de devolver opciones reproducibles entre dos puntos. El criterio de salida es que cada instrucción muestre recorrido, sentido, parada de ascenso, parada de descenso, caminata, tarifa y nivel de confianza.
