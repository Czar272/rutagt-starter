"""Pruebas del cliente HTTP del recolector, sin acceso a la red."""

import io
import json
from types import ModuleType
from typing import Any
from urllib.error import HTTPError, URLError

import pytest


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
def no_sleep(collect: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr(collect.time, "sleep", delays.append)
    return delays


def test_http_get_returns_body_and_lowercase_headers(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested: list[str] = []

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        requested.append(request.full_url)
        return FakeResponse(b"{}", request.full_url, {"Content-Type": "text/json"})

    monkeypatch.setattr(collect, "urlopen", fake_urlopen)

    response = collect.http_get("https://example.test/api?x=1", params={"f": "json"})

    assert requested == ["https://example.test/api?x=1&f=json"]
    assert response.body == b"{}"
    assert response.headers == {"content-type": "text/json"}


def test_http_get_retries_transient_errors_with_backoff(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    calls = 0

    def failing_urlopen(request: Any, timeout: int) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise URLError("sin conexión")

    monkeypatch.setattr(collect, "urlopen", failing_urlopen)

    with pytest.raises(collect.CollectorError, match="No fue posible consultar"):
        collect.http_get("https://example.test", attempts=3)

    assert calls == 3
    assert no_sleep == [0.5, 1.0]


@pytest.mark.parametrize(("code", "expected_calls"), [(404, 1), (429, 2), (503, 2)])
def test_http_get_does_not_retry_client_errors_except_rate_limit(
    collect: ModuleType,
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

    monkeypatch.setattr(collect, "urlopen", http_error)

    with pytest.raises(collect.CollectorError):
        collect.http_get("https://example.test", attempts=2)

    assert calls == expected_calls


def _fake_http(collect: ModuleType, body: bytes) -> Any:
    def fake_http_get(url: str, **_: Any) -> Any:
        return collect.HttpResponse(body=body, final_url=url, status=200, headers={})

    return fake_http_get


def test_get_json_parses_payload(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect, "http_get", _fake_http(collect, b'{"a": 1}'))

    payload, response = collect.get_json("https://example.test")

    assert payload == {"a": 1}
    assert response.final_url == "https://example.test"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"<html>", "JSON inválida"),
        (json.dumps({"error": {"code": 400}}).encode(), "ArcGIS devolvió un error"),
    ],
)
def test_get_json_rejects_invalid_or_error_payloads(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, body: bytes, message: str
) -> None:
    monkeypatch.setattr(collect, "http_get", _fake_http(collect, body))

    with pytest.raises(collect.CollectorError, match=message):
        collect.get_json("https://example.test")
