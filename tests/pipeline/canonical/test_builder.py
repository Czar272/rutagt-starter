"""Pruebas del constructor canónico con lotes sintéticos (ADR-0035)."""

from typing import Any

import pytest

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.pipeline.canonical import builder
from rutagt.pipeline.canonical.models import Agency, CanonicalDataset, Quality, Stop
from rutagt.pipeline.normalizers.models import (
    Issue,
    Position,
    Severity,
    SourceRef,
    StagedRecord,
    StagedRoute,
    StagedShape,
    StagedStop,
    StagingBatch,
)

SNAPSHOT = "20261126T181403Z"
STOPS = "muni_paradas"
ROUTES = "muni_rutas"
LINE: tuple[Position, ...] = ((-90.50, 14.60), (-90.49, 14.60))
OTHER_LINE: tuple[Position, ...] = ((-90.50, 14.61), (-90.49, 14.61))
HERE: Position = (-90.5, 14.6)
FETCHED_AT = "2026-11-26T18:14:09+00:00"
SHA = "0" * 64


def ref(external_id: str, source_id: str = STOPS) -> SourceRef:
    return SourceRef(source_id=source_id, external_id=external_id, raw={"FID": 1})


def stop(
    external_id: str,
    name: str,
    position: Position = HERE,
    *codes: str,
    direction: str | None = None,
) -> StagedStop:
    return StagedStop(
        source=ref(external_id),
        name=name,
        position=position,
        route_codes=codes or ("12000",),
        direction_hint=direction,
        address="3 calle zona 1",
        zone="1",
    )


def route(external_id: str, code: str, variant: str | None, name: str) -> StagedRoute:
    return StagedRoute(
        source=ref(external_id, ROUTES),
        route_code=code,
        variant_code=variant,
        short_name=code,
        long_name=name,
    )


def shape(
    external_id: str,
    code: str,
    variant: str | None,
    coordinates: tuple[Position, ...] = LINE,
) -> StagedShape:
    return StagedShape(
        source=ref(external_id, ROUTES),
        route_code=code,
        variant_code=variant,
        coordinates=coordinates,
        length_m=1077.554,
    )


def batch(
    source_id: str, *records: StagedRecord, issues: tuple[Issue, ...] = ()
) -> StagingBatch:
    return StagingBatch(
        source_id=source_id, snapshot_id=SNAPSHOT, records=records, issues=issues
    )


def source(source_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": source_id,
        "name": source_id,
        "authority": "Municipalidad",
        "catalog_url": "https://datos.example/",
        "agency": "metro",
        "source_kind": "official_open_data",
        **extra,
    }


AGENCIES = [Agency(agency_id="metro", agency_name="Metro")]
NETWORK = batch(
    ROUTES,
    route("1", "12", "12000", "Línea 12"),
    shape("1", "12", "12000"),
    route("2", "12", "12001", "Línea 12 (Directo)"),
    shape("2", "12", "12001"),
    route("3", "7", "7000", "Línea 7"),
    shape("3", "7", "7000", OTHER_LINE),
    issues=(
        Issue(
            severity=Severity.INFO,
            code="tramos_unidos",
            message="2 tramos unidos",
            external_id="3",
        ),
    ),
)


def build(
    stops_batch: StagingBatch, *, group_stations: bool = True, **extra: Any
) -> CanonicalDataset:
    sources = [
        source(ROUTES),
        {
            **source(STOPS, shapes_source=ROUTES, group_stations=group_stations),
            **extra,
        },
    ]
    provenance = {s["id"]: {"fetched_at": FETCHED_AT, "sha256": SHA} for s in sources}
    return builder.build_dataset(
        SNAPSHOT,
        {ROUTES: NETWORK, STOPS: stops_batch},
        sources,
        AGENCIES,
        provenance,
    )


def stops_by_id(dataset: CanonicalDataset) -> dict[str, Stop]:
    return {stop.stop_id: stop for stop in dataset.stops}


def test_routes_variants_and_shared_shapes() -> None:
    dataset = build(batch(STOPS, stop("1", "Estación Bolívar")))

    assert [r.route_id for r in dataset.routes] == [
        "metro:route:7",
        "metro:route:12",
    ]
    route_12 = dataset.routes[1]
    assert (route_12.route_long_name, route_12.source_record.external_id) == (
        "Línea 12",
        "1",
    )
    assert [(p.pattern_id, p.shape_id) for p in dataset.patterns] == [
        ("metro:pattern:7000", "metro:shape:7000"),
        ("metro:pattern:12000", "metro:shape:12000"),
        ("metro:pattern:12001", "metro:shape:12000"),
    ]
    assert [(s.shape_id, s.quality, len(s.records)) for s in dataset.shapes] == [
        ("metro:shape:7000", Quality.PROBABLE, 1),
        ("metro:shape:12000", Quality.OFFICIAL, 2),
    ]
    assert dataset.shapes[1].distance_m == 1077.55


def test_platforms_repeated_by_variant_are_one_stop_in_a_station() -> None:
    east: Position = (-90.4990, 14.6)
    dataset = build(
        batch(
            STOPS,
            stop("44", "Estación Bolívar", HERE, "12000", direction="Plaza Barrios"),
            stop("103", "Estación Bolívar", HERE, "12001"),
            stop("57", "Estación Bolívar", east, "12000", direction="Central Sur"),
            stop("116", "Estación Bolívar", east, "12001"),
        )
    )
    stops = stops_by_id(dataset)

    assert list(stops) == [
        "metro:stop:bolivar",
        "metro:stop:bolivar.1",
        "metro:stop:bolivar.2",
    ]
    station, first, second = stops.values()
    assert (station.location_type, station.parent_station_id) == (1, None)
    assert station.location == (-90.4995, 14.6)
    assert station.location_quality is Quality.PROBABLE
    assert station.records == ()
    assert [r.external_id for r in first.records] == ["44", "103"]
    assert [r.external_id for r in second.records] == ["57", "116"]
    assert (first.parent_station_id, first.platform_code) == (station.stop_id, "1")
    assert (first.direction_hint, second.direction_hint) == (
        "Plaza Barrios",
        "Central Sur",
    )
    assert first.pattern_ids == ("metro:pattern:12000", "metro:pattern:12001")
    assert first.location_quality is Quality.OFFICIAL


def test_station_names_are_unified_with_evidence() -> None:
    dataset = build(
        batch(
            STOPS,
            stop("22", "Estación Atlántida"),
            stop("167", "Atlántida", (-90.4998, 14.6011)),
        )
    )

    assert [s.stop_id for s in dataset.stops] == [
        "metro:stop:atlantida",
        "metro:stop:atlantida.1",
        "metro:stop:atlantida.2",
    ]
    assert dataset.stops[0].stop_name == "Estación Atlántida"
    [issue] = [i for i in dataset.issues if i.issue_type == "nombres_unificados"]
    assert issue.entity_id == "metro:stop:atlantida"
    assert issue.evidence == {
        "severity": "info",
        "nombres": ["Atlántida", "Estación Atlántida"],
    }


def test_dispersed_station_and_contradictory_direction_are_reported() -> None:
    far: Position = (-90.5, 14.6060)
    dataset = build(
        batch(
            STOPS,
            stop("1", "Granai", HERE, direction="La Merced"),
            stop("2", "Granai", HERE, "12001", direction="USAC"),
            stop("3", "Granai", far),
        )
    )
    issues = {(i.issue_type, i.entity_id): i for i in dataset.issues}

    assert issues[("estacion_dispersa", "metro:stop:granai")].evidence[
        "radio_m"
    ] == pytest.approx(333.6, abs=0.5)
    assert issues[("sentido_contradictorio", "metro:stop:granai.1")].evidence == {
        "severity": "warning",
        "sentidos": ["La Merced", "USAC"],
    }
    assert stops_by_id(dataset)["metro:stop:granai.1"].direction_hint is None


def test_stops_without_stations_get_numbered_only_when_names_repeat() -> None:
    dataset = build(
        batch(
            STOPS,
            stop("63", "Parada 067", HERE, "12000"),
            stop("278", "Parada 067", (-90.500004, 14.6), "12001"),
            stop("143", "Parada 190", HERE),
            stop("258", "Parada 190", (-90.49995, 14.6)),
        ),
        group_stations=False,
    )

    assert [(s.stop_id, [r.external_id for r in s.records]) for s in dataset.stops] == [
        ("metro:stop:parada-067", ["63", "278"]),
        ("metro:stop:parada-190.1", ["143"]),
        ("metro:stop:parada-190.2", ["258"]),
    ]
    assert {s.location_type for s in dataset.stops} == {0}
    assert {s.parent_station_id for s in dataset.stops} == {None}


def test_staging_issues_point_to_the_canonical_entity() -> None:
    stops_batch = batch(
        STOPS,
        stop("143", "Parada 190"),
        issues=(
            Issue(
                severity=Severity.WARNING,
                code="numero_repetido",
                message="El número 190 aparece en 2 paradas",
                external_id="143",
                evidence={"external_ids": ["143", "258"]},
            ),
            Issue(severity=Severity.INFO, code="lote", message="Sin registro"),
        ),
    )
    dataset = build(stops_batch, group_stations=False)
    issues = {i.issue_type: i for i in dataset.issues}

    assert (issues["tramos_unidos"].entity_type, issues["tramos_unidos"].entity_id) == (
        "route_pattern",
        "metro:pattern:7000",
    )
    repeated = issues["numero_repetido"]
    assert (repeated.entity_type, repeated.entity_id) == (
        "stop",
        "metro:stop:parada-190",
    )
    assert repeated.evidence == {
        "severity": "warning",
        "external_ids": ["143", "258"],
        "external_id": "143",
    }
    assert (issues["lote"].entity_type, issues["lote"].entity_id) == (
        "data_source",
        STOPS,
    )
    assert build(stops_batch, group_stations=False).issues == dataset.issues


def test_sources_and_records_carry_provenance() -> None:
    dataset = build(batch(STOPS, stop("1", "Estación Bolívar")))

    assert [s.source_id for s in dataset.data_sources] == [STOPS, ROUTES]
    assert dataset.data_sources[0].fetched_at == FETCHED_AT
    assert dataset.data_sources[0].source_url == "https://datos.example/"
    assert [
        (r.source_id, r.external_id, r.entity_type) for r in dataset.source_records
    ] == [
        (STOPS, "1", "stop"),
        (ROUTES, "1", "route"),
        (ROUTES, "2", "route"),
        (ROUTES, "3", "route"),
    ]
    assert dataset.source_records[0].checksum == builder.checksum({"FID": 1})
    assert [a.agency_id for a in dataset.agencies] == ["metro"]


@pytest.mark.parametrize(
    ("change", "error", "message"),
    [
        ({"agency": "otra"}, ConfigurationError, "agencia desconocida"),
        ({"source_kind": None}, ConfigurationError, "no declara 'source_kind'"),
        ({"shapes_source": "falta"}, ConfigurationError, "necesita falta"),
    ],
)
def test_rejects_invalid_configuration(
    change: dict[str, Any], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        build(batch(STOPS, stop("1", "X")), **change)


def test_rejects_batches_with_errors_or_missing() -> None:
    failing = batch(
        STOPS,
        stop("1", "X"),
        issues=(Issue(severity=Severity.ERROR, code="sin_nombre", message="x"),),
    )
    with pytest.raises(SourceError, match="severidad error"):
        build(failing)
    with pytest.raises(SourceError, match="Falta el lote"):
        builder.build_dataset(SNAPSHOT, {}, [source(STOPS)], AGENCIES, {})


def test_rejects_raw_provenance_without_download_data() -> None:
    with pytest.raises(SourceError, match="fetched_at"):
        builder.build_dataset(
            SNAPSHOT,
            {STOPS: batch(STOPS, stop("1", "X"))},
            [source(STOPS)],
            AGENCIES,
            {STOPS: {"sha256": SHA}},
        )
