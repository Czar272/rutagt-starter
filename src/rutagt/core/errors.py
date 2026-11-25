"""Jerarquía de excepciones de RutaGT."""


class RutaGTError(Exception):
    """Error base de RutaGT; toda excepción propia hereda de esta clase."""


class ConfigurationError(RutaGTError):
    """La configuración o el catálogo de fuentes son inválidos."""


class SourceError(RutaGTError):
    """Falla controlada al obtener o procesar una fuente de datos."""
