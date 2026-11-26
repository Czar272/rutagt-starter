"""Límites geográficos de referencia (lon mín., lat mín., lon máx., lat máx.)."""

Bounds = tuple[float, float, float, float]

GUATEMALA_BOUNDS: Bounds = (-92.25, 13.70, -88.20, 17.82)
"""Límites aproximados de Guatemala. Fuera de ellos, una coordenada es un error."""

METRO_AREA_BOUNDS: Bounds = (-90.75, 14.38, -90.30, 14.85)
"""Límites aproximados del Área Metropolitana de Guatemala, la cobertura de RutaGT.

Incluye la capital y los municipios vecinos (Mixco, Villa Nueva, Chinautla,
Santa Catarina Pinula, San José Pinula, San Miguel Petapa, Villa Canales y
Amatitlán). Se reemplazará por los polígonos oficiales cuando se incorporen.
"""


def contains(bounds: Bounds, lon: float, lat: float) -> bool:
    """Indica si la posición está dentro de los límites, bordes incluidos."""
    min_lon, min_lat, max_lon, max_lat = bounds
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
