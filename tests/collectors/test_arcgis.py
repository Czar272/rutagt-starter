"""Pruebas de descubrimiento y descarga de capas ArcGIS con respuestas simuladas."""

import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SERVICE_URL = "https://services.example.test/arcgis/rest/services/paradas/FeatureServer"
ITEM_URL = "https://www.arcgis.com/sharing/rest/content/items/{item_id}"
SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"

SOURCE: dict[str, Any] = {
    "id": "fuente_prueba",
    "name": "Fuente de prueba",
    "type": "arcgis_feature_service",
    "authority": "Autoridad de prueba",
    "discover_query": 'title:"PARADAS"',
    "fallback_item_id": "respaldo",
    "layer": 0,
    "output": "prueba/paradas.geojson",
    "expected_geometry": ["Point"],
    "required_fields": ["Nombre"],
}


def point(fid: int) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
        "properties": {"FID": fid, "Nombre": f"Parada {fid}"},
    }


Router = Callable[[str, dict[str, Any] | None], tuple[Any, Any]]


def install_router(
    collect: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    routes: dict[str, Any],
    calls: list[tuple[str, dict[str, Any] | None]] | None = None,
) -> None:
    """Sustituye `get_json` por respuestas fijas indexadas por URL."""

    def fake_get_json(url: str, params: dict[str, Any] | None = None) -> Any:
        if calls is not None:
            calls.append((url, params))
        value = routes[url]
        payload = value(params) if callable(value) else value
        response = collect.HttpResponse(b"", url, 200, {})
        return payload, response

    monkeypatch.setattr(collect, "get_json", fake_get_json)


def test_discover_prefers_latest_public_feature_service(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    results = [
        {"id": "privado", "type": "Feature Service", "access": "private"},
        {"id": "mapa", "type": "Web Map", "access": "public"},
        {"id": "vigente", "type": "Feature Service", "access": "public"},
    ]
    install_router(collect, monkeypatch, {SEARCH_URL: {"results": results}})

    assert collect.discover_arcgis_item(SOURCE)["id"] == "vigente"


def test_discover_uses_fallback_item_when_search_is_empty(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_router(
        collect,
        monkeypatch,
        {
            SEARCH_URL: {"results": []},
            ITEM_URL.format(item_id="respaldo"): {"id": "respaldo", "url": SERVICE_URL},
        },
    )

    assert collect.discover_arcgis_item(SOURCE)["url"] == SERVICE_URL


@pytest.mark.parametrize(
    ("source", "routes"),
    [
        ({**SOURCE, "fallback_item_id": None}, {SEARCH_URL: {"results": []}}),
        (
            {**SOURCE, "discover_query": None},
            {ITEM_URL.format(item_id="respaldo"): {"id": "respaldo"}},
        ),
    ],
    ids=["sin-respaldo", "respaldo-sin-url"],
)
def test_discover_fails_without_usable_item(
    collect: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    source: dict[str, Any],
    routes: dict[str, Any],
) -> None:
    install_router(collect, monkeypatch, routes)

    with pytest.raises(collect.CollectorError):
        collect.discover_arcgis_item(source)


@pytest.mark.parametrize(
    ("service_url", "expected"),
    [
        (SERVICE_URL, f"{SERVICE_URL}/0"),
        (f"{SERVICE_URL}/", f"{SERVICE_URL}/0"),
        (f"{SERVICE_URL}/3", f"{SERVICE_URL}/3"),
    ],
)
def test_layer_url(collect: ModuleType, service_url: str, expected: str) -> None:
    assert collect.layer_url(service_url, 0) == expected


def test_collect_arcgis_paginates_and_writes_provenance(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = {
        0: {
            "features": [point(1), point(2)],
            "properties": {"exceededTransferLimit": True},
        },
        2: {"features": [point(3)]},
    }
    calls: list[tuple[str, dict[str, Any] | None]] = []
    install_router(
        collect,
        monkeypatch,
        {
            SEARCH_URL: {"results": []},
            ITEM_URL.format(item_id="respaldo"): {
                "id": "respaldo",
                "url": SERVICE_URL,
                "title": "PARADAS",
                "owner": "digm",
            },
            f"{SERVICE_URL}/0": {"objectIdField": "FID", "maxRecordCount": 2},
            f"{SERVICE_URL}/0/query": lambda params: pages[params["resultOffset"]],
        },
        calls,
    )
    destination = tmp_path / SOURCE["output"]

    metadata = collect.collect_arcgis(SOURCE, destination)

    collection = json.loads(destination.read_text(encoding="utf-8"))
    provenance = json.loads(
        destination.with_name("paradas.geojson.provenance.json").read_text(
            encoding="utf-8"
        )
    )
    query_params = [params for url, params in calls if url.endswith("/query")]
    assert [p["resultOffset"] for p in query_params if p] == [0, 2]
    assert all(p and p["orderByFields"] == "FID" for p in query_params)
    assert [f["properties"]["FID"] for f in collection["features"]] == [1, 2, 3]
    assert metadata["record_count"] == 3
    assert metadata["quality_warnings"] == []
    assert provenance["resolved_layer_url"] == f"{SERVICE_URL}/0"
    assert provenance["arcgis"]["object_id_field"] == "FID"
    assert len(provenance["sha256"]) == 64


def test_collect_arcgis_requires_service_url(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(collect, "discover_arcgis_item", lambda source: {"id": None})

    with pytest.raises(collect.CollectorError, match="URL del Feature Service"):
        collect.collect_arcgis({**SOURCE, "fallback_item_id": None}, tmp_path / "x")
