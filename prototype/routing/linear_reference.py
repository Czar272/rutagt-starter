"""Referenciación lineal: posición de un punto a lo largo de un trazado.

Proyecta coordenadas [lon, lat] sobre una polilínea usando una aproximación
equirectangular local, suficiente para distancias urbanas (error < 0,1 %).
"""

import math
from dataclasses import dataclass

METERS_PER_DEGREE_LAT = 110_540
METERS_PER_DEGREE_LON_EQUATOR = 111_320


@dataclass(frozen=True)
class Projection:
    """Resultado de proyectar un punto sobre el trazado."""

    position_m: float
    """Distancia recorrida desde el inicio del trazado hasta el punto proyectado."""

    offset_m: float
    """Distancia perpendicular entre el punto y el trazado."""


class Polyline:
    """Trazado de una ruta en metros, con distancias acumuladas."""

    def __init__(self, coordinates: list[list[float]]) -> None:
        reference_lat = sum(point[1] for point in coordinates) / len(coordinates)
        self._kx = METERS_PER_DEGREE_LON_EQUATOR * math.cos(math.radians(reference_lat))
        self._points = [self._to_meters(point) for point in coordinates]
        self._cumulative = [0.0]
        for start, end in zip(self._points, self._points[1:], strict=False):
            self._cumulative.append(self._cumulative[-1] + math.dist(start, end))

    @property
    def length_m(self) -> float:
        return self._cumulative[-1]

    def _to_meters(self, point: list[float]) -> tuple[float, float]:
        return (point[0] * self._kx, point[1] * METERS_PER_DEGREE_LAT)

    def project(self, point: list[float]) -> Projection:
        """Proyecta un punto [lon, lat] sobre el segmento más cercano del trazado."""
        px, py = self._to_meters(point)
        best = Projection(position_m=0.0, offset_m=math.inf)
        for index, (start, end) in enumerate(
            zip(self._points, self._points[1:], strict=False)
        ):
            dx, dy = end[0] - start[0], end[1] - start[1]
            squared = dx * dx + dy * dy
            ratio = (
                0.0
                if squared == 0
                else max(
                    0.0,
                    min(1.0, ((px - start[0]) * dx + (py - start[1]) * dy) / squared),
                )
            )
            nearest = (start[0] + ratio * dx, start[1] + ratio * dy)
            offset = math.dist((px, py), nearest)
            if offset < best.offset_m:
                best = Projection(
                    position_m=self._cumulative[index] + ratio * math.sqrt(squared),
                    offset_m=offset,
                )
        return best
