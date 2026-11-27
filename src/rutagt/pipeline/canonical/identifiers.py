"""Identificadores canónicos `<agencia>:<tipo>:<código>` (ADR-0029, ADR-0035).

Los códigos salen del dato publicado (código de ruta o variante, nombre de la
estación o parada), no del `FID` de la capa, que la Municipalidad puede
renumerar al republicarla.
"""

import re
import unicodedata

_NOT_ALNUM = re.compile(r"[^a-z0-9]+")
_STATION_PREFIX = re.compile(r"^estacion-")


def slug(text: str) -> str:
    """Texto en ASCII con guiones: «Estación Bolívar» da `estacion-bolivar`."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return _NOT_ALNUM.sub("-", ascii_text.lower()).strip("-")


def place_key(name: str) -> str:
    """Clave de un lugar por su nombre, sin el prefijo «Estación».

    «Estación Atlántida», «Atlántida» y «Estacion Atlantida» dan `atlantida`.
    """
    return _STATION_PREFIX.sub("", slug(name)) or slug(name)


def entity_id(agency_id: str, kind: str, code: str) -> str:
    """Identificador canónico de una entidad de la red."""
    return f"{agency_id}:{kind}:{code}"


def code_order(code: str) -> tuple[int, int, str]:
    """Orden natural de códigos: numéricos por valor y luego el resto."""
    return (0, int(code), "") if code.isdigit() else (1, 0, code)
