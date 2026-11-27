"""Pruebas de la secuencia de paradas por variante (ADR-0036)."""

from typing import Any

import pytest

from rutagt.core.errors import ConfigurationError
from rutagt.pipeline.canonical import builder, sequences
from rutagt.pipeline.canonical.models import (
    Agency,
    Position,
    Quality,
    RecordRef,
    Rutero,
    RuteroStop,
    Shape,
    Stop,
)
from rutagt.pipeline.normalizers.models import (
    SourceRef,
    StagedRoute,
    StagedShape,
    StagedStop,
    StagingBatch,
)

SNAPSHOT = "20261126T181403Z"
# Recorrido de ida y vuelta: sale hacia el este y regresa al punto de partida.
LOOP: tuple[Position, ...] = (
    (-90.500, 14.600),
    (-90.490, 14.600),
    (-90.490, 14.601),
    (-90.500, 14.601),
    (-90.500, 14.600),
)
LINE: tuple[Position, ...] = ((-90.500, 14.600), (-90.490, 14.600))
ADDRESSES = {
    "a": "33 avenida y 39 calle, Colonia El Amparo",
    "b": "Calzada San Juan y 8a avenida",
    "c": "Anillo Periférico y 31 avenida",
    "d": "Boulevard Liberación y 6a avenida",
}


def stop(code: str, position: Position, address: str | None = None) -> Stop:
    return Stop(
        stop_id=f"tubus:stop:{code}",
        stop_name=code,
        location_type=0,
        location=position,
        location_quality=Quality.OFFICIAL,
        address=address if address is not None else ADDRESSES.get(code),
        zone=None,
        parent_station_id=None,
        platform_code=None,
        direction_hint=None,
        pattern_ids=("tubus:pattern:801",),
        source_id="paradas",
        source_record=RecordRef(source_id="paradas", external_id=code),
        records=(RecordRef(source_id="paradas", external_id=code),),
    )


def shape(coordinates: tuple[Position, ...]) -> Shape:
    ref = RecordRef(source_id="rutas", external_id="1")
    return Shape(
        shape_id="tubus:shape:801",
        coordinates=coordinates,
        distance_m=1000.0,
        quality=Quality.OFFICIAL,
        source_id="rutas",
        source_record=ref,
        records=(ref,),
    )


def rutero(*codes: str, reviewed: dict[str, str] | None = None) -> Rutero:
    return Rutero(
        schema_version=1,
        source_id="rutero_801",
        agency_id="tubus",
        pattern_code="801",
        route_name="Ruta 801",
        terminal_stop_code=codes[-1],
        source={
            "document_sha256": "0" * 64,
            "validation": {"validated_at": "2026-11-25"},
        },
        stops=tuple(
            RuteroStop(
                sequence=number,
                stop_code=code,
                address=ADDRESSES[code],
                layer_external_id=(reviewed or {}).get(code),
            )
            for number, code in enumerate(codes, start=1)
        ),
    )


@pytest.mark.parametrize(
    ("address", "numbers"),
    [
        ("Calz. San Juan y 8a avenida", {("8", "av")}),
        ("33 avenida y 39 calle, zona 7", {("33", "av"), ("39", "calle")}),
        ("Calle 5 y Diagonal 6", {("5", "calle"), ("6", "diagonal")}),
        ("Parque Los Pinos", set()),
        (None, set()),
    ],
)
def test_street_numbers(address: str | None, numbers: set[tuple[str, str]]) -> None:
    assert sequences.street_numbers(address) == numbers


def test_address_score_distinguishes_street_numbers() -> None:
    same = sequences.address_score("8a avenida y 3a calle", "8 avenida y 3 calle")
    other = sequences.address_score("8a avenida y 3a calle", "9a avenida y 3a calle")

    # Sin números de vía, la coincidencia de números es neutral.
    assert sequences.address_score("Calzada San Juan", "calzada san juan") == 0.8
    assert sequences.address_score("8a avenida", "8a  Avenida") == 1.0
    assert same > sequences.MATCH_THRESHOLD > other


def test_align_in_order_keeps_order_and_skips_columns() -> None:
    columns, total = sequences.align_in_order([[0.9, 0.1, 0.8], [0.2, 0.1, 0.9]])

    assert columns == [0, 2]
    assert total == pytest.approx(1.8)
    with pytest.raises(ValueError, match="menos paradas"):
        sequences.align_in_order([[1.0], [1.0]])


def test_project_measures_along_the_shape() -> None:
    projection = sequences.project((-90.495, 14.6001), LINE)

    assert projection.position_m == pytest.approx(538.8, abs=1)
    assert projection.offset_m == pytest.approx(11.1, abs=0.5)


def test_without_rutero_stops_follow_the_shape() -> None:
    stops = [
        stop("c", (-90.495, 14.601)),
        stop("a", (-90.499, 14.600)),
        stop("b", (-90.491, 14.600)),
    ]
    result = sequences.sequence_without_rutero("tubus:pattern:801", shape(LOOP), stops)

    assert [p.stop_id for p in result.pattern_stops] == [
        "tubus:stop:a",
        "tubus:stop:b",
        "tubus:stop:c",
    ]
    assert {p.sequence_quality for p in result.pattern_stops} == {Quality.PROBABLE}
    assert sequences.is_circuit(shape(LOOP))
    assert not sequences.is_circuit(shape(LINE))


def test_rutero_on_a_circuit_may_start_anywhere() -> None:
    # El rutero empieza en «c», a mitad del trazado, y da la vuelta.
    stops = [
        stop("a", (-90.499, 14.600)),
        stop("b", (-90.491, 14.600)),
        stop("c", (-90.495, 14.601)),
        stop("x", (-90.4995, 14.6008), "Sin relación"),
    ]
    result = sequences.sequence_with_rutero(
        "tubus:pattern:801", shape(LOOP), stops, rutero("c", "a", "b")
    )

    assert [p.stop_id for p in result.pattern_stops] == [
        "tubus:stop:c",
        "tubus:stop:a",
        "tubus:stop:b",
    ]
    assert [s.stop_id for s in result.unassigned] == ["tubus:stop:x"]
    # Un recorrido que no empieza en el inicio del trazado no tiene distancias.
    assert {p.shape_dist_traveled_m for p in result.pattern_stops} == {None}


def test_review_confirms_or_contradicts_the_assignment() -> None:
    stops = [
        stop("a", (-90.499, 14.600), "Otra dirección"),
        stop("b", (-90.491, 14.600)),
    ]
    result = sequences.sequence_with_rutero(
        "tubus:pattern:801",
        shape(LINE),
        stops,
        rutero("a", "b", reviewed={"a": "a", "b": "zz"}),
    )

    assert [a.confirmed for a in result.assignments] == [True, False]
    assert [p.sequence_quality for p in result.pattern_stops] == [
        Quality.OFFICIAL,
        Quality.PROBABLE,
    ]
    assert result.pattern_stops[1].shape_dist_traveled_m is not None


# ---------------------------------------------------------------------------
# Integración con el constructor
# ---------------------------------------------------------------------------


def ref(external_id: str, source_id: str) -> SourceRef:
    return SourceRef(source_id=source_id, external_id=external_id, raw={})


def staged_stop(external_id: str, name: str, position: Position) -> StagedStop:
    return StagedStop(
        source=ref(external_id, "paradas"),
        name=name,
        position=position,
        route_codes=("801",),
        address=ADDRESSES.get(name),
    )


def build(*ruteros: Rutero, stops: tuple[StagedStop, ...] | None = None) -> Any:
    routes = StagingBatch(
        source_id="rutas",
        snapshot_id=SNAPSHOT,
        records=(
            StagedRoute(source=ref("1", "rutas"), route_code="801", short_name="801"),
            StagedShape(
                source=ref("1", "rutas"),
                route_code="801",
                coordinates=LINE,
                length_m=1077.6,
            ),
        ),
    )
    paradas = StagingBatch(
        source_id="paradas",
        snapshot_id=SNAPSHOT,
        records=stops
        or (
            staged_stop("1", "a", (-90.499, 14.600)),
            staged_stop("2", "b", (-90.491, 14.600)),
        ),
    )
    base = {
        "name": "x",
        "agency": "tubus",
        "source_kind": "official_open_data",
        "catalog_url": "https://datos.example/",
    }
    sources = [
        {**base, "id": "rutas"},
        {**base, "id": "paradas", "shapes_source": "rutas"},
    ]
    return builder.build_dataset(
        SNAPSHOT,
        {"rutas": routes, "paradas": paradas},
        sources,
        [Agency(agency_id="tubus", agency_name="TuBus")],
        {
            s["id"]: {"fetched_at": "2026-11-26T18:14:09+00:00", "sha256": "0" * 64}
            for s in sources
        },
        ruteros,
    )


def issue_types(dataset: Any) -> dict[str, Any]:
    return {i.issue_type: i for i in dataset.issues}


def test_builder_assigns_official_codes_and_terminal() -> None:
    dataset = build(rutero("a", "b"))
    stops = {s.stop_id: s for s in dataset.stops}

    assert [p.stop_id for p in dataset.pattern_stops] == [
        "tubus:stop:a",
        "tubus:stop:b",
    ]
    assert stops["tubus:stop:a"].stop_code == "a"
    assert dataset.patterns[0].attributes == {
        "circuit": False,
        "sequence_source": "rutero_801",
        "terminal_stop_id": "tubus:stop:b",
    }
    assert [s.source_id for s in dataset.data_sources] == [
        "paradas",
        "rutas",
        "rutero_801",
    ]
    assert "secuencia_sin_rutero" not in issue_types(dataset)


def test_builder_reports_unconfirmed_assignments() -> None:
    dataset = build(
        rutero("a", "b"),
        stops=(
            staged_stop("1", "a", (-90.499, 14.600)),
            staged_stop("2", "otra", (-90.491, 14.600)),
        ),
    )
    issue = issue_types(dataset)["parada_por_revisar"]

    assert issue.entity_id == "tubus:stop:otra"
    assert issue.evidence["revision"] is None
    assert [p.sequence_quality for p in dataset.pattern_stops] == [
        Quality.OFFICIAL,
        Quality.PROBABLE,
    ]


def test_builder_reports_contradicted_reviews() -> None:
    dataset = build(rutero("a", "b", reviewed={"a": "1", "b": "9"}))

    issue = issue_types(dataset)["asignacion_contradice_revision"]
    assert (issue.entity_id, issue.evidence["revision"]) == ("tubus:stop:b", "9")


def test_builder_falls_back_when_the_rutero_has_more_stops() -> None:
    dataset = build(rutero("a", "b", "c"))
    issues = issue_types(dataset)

    assert issues["rutero_incompleto"].evidence == {
        "severity": "warning",
        "rutero": 3,
        "capa": 2,
    }
    assert "secuencia_sin_rutero" in issues
    assert dataset.patterns[0].attributes["sequence_source"] == "trazado"


def test_builder_warns_about_ruteros_of_missing_patterns() -> None:
    other = rutero("a", "b").model_copy(update={"pattern_code": "999"})
    dataset = build(other)

    assert issue_types(dataset)["rutero_sin_variante"].evidence["pattern_id"] == (
        "tubus:pattern:999"
    )


def test_builder_rejects_two_ruteros_for_one_pattern() -> None:
    with pytest.raises(ConfigurationError, match="dos ruteros"):
        build(rutero("a", "b"), rutero("a", "b"))


def test_builder_rejects_ruteros_without_validation() -> None:
    unvalidated = rutero("a", "b").model_copy(update={"source": {}})

    with pytest.raises(ConfigurationError, match="document_sha256"):
        build(unvalidated)


def test_contradictory_official_codes_are_not_assigned() -> None:
    issues = builder._Issues()
    [result] = builder._official_codes(
        [stop("a", (-90.499, 14.600))], {"tubus:stop:a": {"067", "068"}}, issues
    )

    assert result.stop_code is None
    assert [(i.issue_type, i.evidence["codigos"]) for i in issues.items] == [
        ("codigo_contradictorio", ["067", "068"])
    ]
