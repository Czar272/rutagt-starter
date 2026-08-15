# RutaGT Starter

Base inicial para organizar un planificador multimodal de transporte público en el área metropolitana de Guatemala.

## Qué incluye

- `docs/plan-producto-y-datos.md`: alcance, datos exactos, fuentes, módulos, arquitectura y fases.
- `docs/solicitudes-informacion.md`: plantillas listas para municipalidades, DGT y operadores.
- `config/sources.json`: catálogo versionado de fuentes verificadas.
- `src/collect.py`: recolector reproducible de ArcGIS Feature Services y páginas de referencia.
- `schema/canonical.sql`: modelo canónico PostgreSQL/PostGIS inspirado en GTFS y ampliado para operación, tarifas, calidad y tiempo real.
- `tests/test_collect.py`: pruebas unitarias del recolector.

## Punto de partida verificado

Las capas públicas actuales de la Municipalidad de Guatemala permiten obtener:

- 169 paradas de Transmetro.
- 278 paradas de TuBus.
- 12 geometrías de rutas de Transmetro.
- 8 geometrías de rutas de TuBus.

Son una buena base cartográfica, pero no bastan para calcular un viaje completo: faltan secuencia confiable por sentido, calendarios, frecuencias, tarifas estructuradas, transbordos y telemetría. El recolector conserva el dato original, genera procedencia y detecta campos o caracteres problemáticos; cualquier corrección debe ir en una capa derivada y auditable.

## Requisitos

- Python 3.10 o posterior.
- PostgreSQL con PostGIS para instalar el esquema (opcional en esta etapa).
- Conexión a Internet para recolectar fuentes.

El recolector usa únicamente la biblioteca estándar de Python.

## Uso rápido

Desde esta carpeta:

```powershell
python src/collect.py list
python src/collect.py fetch --all --output data/raw
python -m unittest discover -s tests -v
```

También se puede descargar una sola fuente:

```powershell
python src/collect.py fetch --source muniguate_transmetro_stops_2025 --output data/raw
```

Cada descarga crea:

- el archivo original normalizado como GeoJSON o JSON;
- un archivo `*.provenance.json` con URL final, fecha UTC, checksum SHA-256, conteos, campos, licencia declarada y alertas de validación;
- un manifiesto de la ejecución.

Una ejecución parcial no borra descargas anteriores. Si una fuente falla, el manifiesto registra el error y el proceso continúa con las demás.

## Flujo recomendado

1. Recolectar las capas oficiales públicas sin modificarlas.
2. Conseguir secuencias, calendarios, frecuencias, tarifas y licencias mediante las solicitudes preparadas.
3. Crear una capa de depuración con reglas y revisiones humanas; no sobrescribir el origen.
4. Publicar un primer feed GTFS de Transmetro y TuBus.
5. Probar un corredor de extremo a extremo, por ejemplo Metrocentro/Villa Nueva–UVG.
6. Añadir Transurbano, TransMIO, Express/municipales y extraurbanos por acuerdos y entregas verificables.
7. Incorporar AVL/GTFS-Realtime y predicción de llegada solo después de estabilizar la red estática.

## Decisiones importantes

- La unidad de ruteo no es solo la línea: es `ruta + variante + sentido + calendario`.
- Las fuentes, licencias y vigencias son datos de primera clase.
- Un horario publicado y una observación real nunca se mezclan sin indicar su origen.
- No se debe extraer una app privada por ingeniería inversa ni publicar datos sin permiso.
- El costo de ruta debe permitir preferencias: tiempo, menos transbordos, menos caminata, menor costo y accesibilidad.

## Próximo hito sugerido

Completar un piloto estático validado para Transmetro y TuBus, capaz de devolver opciones reproducibles entre dos puntos. El criterio de salida es que cada instrucción muestre recorrido, sentido, parada de ascenso, parada de descenso, caminata, tarifa y nivel de confianza.
