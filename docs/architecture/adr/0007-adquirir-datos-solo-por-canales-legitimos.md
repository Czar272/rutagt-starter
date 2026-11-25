# ADR-0007: Adquirir datos solo por canales legítimos

| Campo       | Valor                  |
| ----------- | ---------------------- |
| Estado      | Aceptado               |
| Fecha       | 2026-08-15             |
| Decisores   | @Czar272               |
| Tickets     | RGT-21, RGT-24         |
| Reemplaza a | —                      |

## Contexto

Parte de la información de transporte existe en aplicaciones privadas (TuBus, SIGA, Moovit, Google Maps, Waze) o en redes sociales. Extraerla mediante ingeniería inversa o raspado sin permiso expondría al proyecto a riesgos legales, a bloqueos técnicos y a la imposibilidad de ser adoptado por instituciones públicas o de comercializarse.

## Decisión

RutaGT obtiene datos **únicamente** mediante:

1. Portales de datos abiertos y publicaciones oficiales.
2. Solicitudes de información pública (Decreto 57-2008, Ley de Acceso a la Información Pública).
3. Convenios técnicos o comerciales con operadores y proveedores.
4. Fuentes abiertas con licencia compatible (OpenStreetMap, con atribución y cumplimiento de ODbL).
5. Levantamiento de campo propio y reportes comunitarios moderados.

No se realiza ingeniería inversa de aplicaciones ni APIs privadas, ni se raspan servicios cuyos términos no lo permitan. Sus páginas públicas pueden usarse solo como verificación manual. Cada fuente se clasifica como automatizable o manual en `config/sources.json` y en la documentación de fuentes, con su nota de licencia.

## Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
| --- | --- | --- | --- |
| Raspar aplicaciones privadas | Cobertura inmediata | Riesgo legal, fragilidad, imposibilita acuerdos institucionales | Incompatible con los objetivos del proyecto |
| Copiar bases de terceros | Rapidez | Infringe términos y derechos sobre la base de datos | Mismo motivo |

## Consecuencias

### Positivas

- El proyecto puede presentarse ante instituciones y potenciales compradores con un origen de datos defendible.
- Las fuentes son estables porque se basan en acuerdos o publicaciones oficiales.

### Negativas y riesgos

- La cobertura crece más lento y depende de respuestas institucionales.
- Requiere gestionar solicitudes y licencias como trabajo explícito (RGT-49, RGT-111).

## Verificación

- Toda fuente de `config/sources.json` tiene `authority` y `license_note`.
- Las solicitudes institucionales están documentadas en `docs/institutions/solicitudes-informacion.md`.

## Referencias

- `docs/data/plan-producto-y-datos.md`, sección 5 «Fuentes que no deben rasparse sin permiso».
- [Decreto 57-2008, Ley de Acceso a la Información Pública](https://www.congreso.gob.gt/detalle_pdf/decretos/13082).
- [OpenStreetMap — Copyright and License](https://www.openstreetmap.org/copyright).
