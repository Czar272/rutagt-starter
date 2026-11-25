"""Cliente HTTP de los collectors: solo http/https, reintentos y respuestas JSON."""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from rutagt.core.errors import SourceError

logger = logging.getLogger(__name__)

USER_AGENT = "RutaGT-data-collector/0.1 (+contacto-pendiente)"
DEFAULT_TIMEOUT = 45
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class HttpResponse:
    """Respuesta HTTP ya leída en memoria."""

    body: bytes
    final_url: str
    status: int
    headers: dict[str, str]


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, HTTPError):
        return error.code == 429 or error.code >= 500
    return True


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = 3,
) -> HttpResponse:
    """Descarga una URL con reintentos y espera exponencial.

    Solo se permiten los esquemas http y https. Los errores 4xx (excepto 429)
    no se reintentan.
    """
    scheme = urlparse(url).scheme.lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise SourceError(f"Esquema de URL no permitido ({scheme or 'vacío'}): {url}")
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"

    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(  # noqa: S310
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            },
        )
        try:
            # El esquema se valida al inicio de la función: solo http y https.
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                return HttpResponse(
                    body=response.read(),
                    final_url=response.geturl(),
                    status=getattr(response, "status", 200),
                    headers={
                        key.lower(): value for key, value in response.headers.items()
                    },
                )
        except (HTTPError, URLError, TimeoutError) as exc:
            error = exc
            if not _is_retryable(exc):
                break
            if attempt < attempts:
                delay = 0.5 * (2 ** (attempt - 1))
                logger.warning(
                    "Reintento %d/%d de %s en %.1f s: %s",
                    attempt,
                    attempts - 1,
                    url,
                    delay,
                    exc,
                )
                time.sleep(delay)
    raise SourceError(f"No fue posible consultar {url}: {error}")


def get_json(
    url: str, params: dict[str, Any] | None = None
) -> tuple[Any, HttpResponse]:
    """Descarga y decodifica una respuesta JSON; rechaza errores de ArcGIS."""
    response = http_get(url, params=params)
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(
            f"Respuesta JSON inválida de {response.final_url}: {exc}"
        ) from exc
    if isinstance(payload, dict) and payload.get("error"):
        raise SourceError(f"El servicio devolvió un error: {payload['error']}")
    return payload, response
