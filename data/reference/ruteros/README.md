# Ruteros oficiales transcritos

Secuencias oficiales de paradas por variante, transcritas de los ruteros que publica la Municipalidad de Guatemala (Dirección de Movilidad Urbana). El constructor canónico (`rutagt-canonical`) las usa para fijar la secuencia de su variante ([ADR-0036](../../../docs/architecture/adr/0036-secuencia-de-paradas-por-variante.md)).

| Archivo          | Variante            | Documento                                   | Validación                                  |
| ---------------- | ------------------- | ------------------------------------------- | ------------------------------------------- |
| `tubus_801.json` | `tubus:pattern:801` | Rutero individual ruta 801, versión 4 (PDF) | 47 de 47 paradas contra el PDF (RGT-127)    |

## Formato

- `source_id`: identificador de la fuente en `provenance.data_source`.
- `agency_id` y `pattern_code`: variante a la que pertenece (`<agency_id>:pattern:<pattern_code>`).
- `terminal_stop_code`: parada terminal, donde cambia el sentido.
- `source`: documento, URL, SHA-256 del PDF y validación de la transcripción. `document_sha256` y `validation.validated_at` son obligatorios.
- `stops`: secuencia, código, dirección y zona de cada parada, tal como en el PDF. `layer_external_id` es el registro de la capa de paradas que eligió la revisión manual.
- `review` y `excluded_layer_records`: revisión manual de la correspondencia con la capa y registros que dejó fuera, con su motivo.

## Agregar un rutero

1. Transcribir la tabla del PDF oficial y validarla contra el documento (código, dirección y zona de cada parada).
2. Registrar el SHA-256 del PDF y la fecha de validación.
3. Ejecutar `uv run rutagt-canonical` y revisar las incidencias `parada_por_revisar` y `parada_fuera_de_rutero` antes de agregar `layer_external_id`.

Los datos son de uso público con atribución a la Municipalidad de Guatemala, Dirección de Movilidad Urbana.
