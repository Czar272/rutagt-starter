"""Pruebas del cliente HTTP de los collectors, sin acceso a la red."""

import io
import json
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from rutagt.core.errors import SourceError
from rutagt.pipeline.collectors import http


class FakeResponse:
    def __init__(self, body: bytes, url: str, headers: dict[str, str]) -> None:
        self._body = body
        self._url = url
        self.status = 200
        self.headers = headers

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr("rutagt.pipeline.collectors.http.time.sleep", delays.append)
    return delays


def test_http_get_returns_body_and_lowercase_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        requested.append(request.full_url)
        return FakeResponse(b"{}", request.full_url, {"Content-Type": "text/json"})

    monkeypatch.setattr(http, "urlopen", fake_urlopen)

    response = http.http_get("https://example.test/api?x=1", params={"f": "json"})

    assert requested == ["https://example.test/api?x=1&f=json"]
    assert response.body == b"{}"
    assert response.headers == {"content-type": "text/json"}


def test_http_get_retries_transient_errors_with_backoff(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    calls = 0

    def failing_urlopen(request: Any, timeout: int) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise URLError("sin conexión")

    monkeypatch.setattr(http, "urlopen", failing_urlopen)

    with pytest.raises(SourceError, match="No fue posible consultar"):
        http.http_get("https://example.test", attempts=3)

    assert calls == 3
    assert no_sleep == [0.5, 1.0]


@pytest.mark.parametrize(("code", "expected_calls"), [(404, 1), (429, 2), (503, 2)])
def test_http_get_does_not_retry_client_errors_except_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    no_sleep: list[float],
    code: int,
    expected_calls: int,
) -> None:
    calls = 0

    def http_error(request: Any, timeout: int) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise HTTPError(request.full_url, code, "error", {}, io.BytesIO())  # type: ignore[arg-type]

    monkeypatch.setattr(http, "urlopen", http_error)

    with pytest.raises(SourceError):
        http.http_get("https://example.test", attempts=2)

    assert calls == expected_calls


def _fake_http(body: bytes) -> Any:
    def fake_http_get(url: str, **_: Any) -> Any:
        return http.HttpResponse(body=body, final_url=url, status=200, headers={})

    return fake_http_get


def test_get_json_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "http_get", _fake_http(b'{"a": 1}'))

    payload, response = http.get_json("https://example.test")

    assert payload == {"a": 1}
    assert response.final_url == "https://example.test"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"<html>", "JSON inválida"),
        (
            json.dumps({"error": {"code": 400}}).encode(),
            "El servicio devolvió un error",
        ),
    ],
)
def test_get_json_rejects_invalid_or_error_payloads(
    monkeypatch: pytest.MonkeyPatch, body: bytes, message: str
) -> None:
    monkeypatch.setattr(http, "http_get", _fake_http(body))

    with pytest.raises(SourceError, match=message):
        http.get_json("https://example.test")


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.test/data", "datos.json"]
)
def test_http_get_rejects_non_http_schemes(url: str) -> None:
    with pytest.raises(SourceError, match="Esquema de URL no permitido"):
        http.http_get(url, attempts=1)
