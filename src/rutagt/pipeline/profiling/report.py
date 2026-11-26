"""Reporte en Markdown de los perfiles de datasets."""

from typing import Any


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key} ({count})" for key, count in counts.items()) or "—"


def _values(field: dict[str, Any]) -> str:
    if field["unique"]:
        return "—"
    if "values" in field:
        pairs = field["values"]
    elif field["top_repeated"]:
        pairs = field["top_repeated"]
    else:
        return "—"
    return ", ".join(f"{_cell(value)} ({count})" for value, count in pairs)


def _range(field: dict[str, Any]) -> str:
    if "min" in field:
        return f"{field['min']} – {field['max']}"
    if "length" in field:
        return f"{field['length'][0]} – {field['length'][1]} caracteres"
    return "—"


def render_dataset(name: str, profile: dict[str, Any]) -> str:
    """Sección de un dataset: resumen, geometrías, campos y anomalías."""
    geometry = profile["geometry"]
    bbox = geometry["bbox"]
    lines = [
        f"## `{name}`",
        "",
        f"- Registros: **{profile['records']}**",
        f"- Geometrías: {_counts(geometry['types'])}",
        "- Extensión (lon/lat): "
        + (
            f"{bbox[0]:.5f}, {bbox[1]:.5f} → {bbox[2]:.5f}, {bbox[3]:.5f}"
            if bbox
            else "—"
        ),
        "",
        "| Campo | Tipos | Nulos/vacíos | Distintos | Único | Rango "
        "| Valores o repetidos más frecuentes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for field_name, field in profile["fields"].items():
        types = _counts(field["types"])
        lines.append(
            f"| `{field_name}` | {types} | {field['null'] + field['empty']} "
            f"| {field['distinct']} | {'sí' if field['unique'] else 'no'} "
            f"| {_range(field)} | {_values(field)} |"
        )
    lines += ["", "**Anomalías detectadas automáticamente:**", ""]
    lines += [f"- {a}" for a in profile["anomalies"]] or ["- Ninguna"]
    return "\n".join(lines) + "\n"


def render_report(snapshot_id: str, profiles: dict[str, dict[str, Any]]) -> str:
    """Reporte completo de todos los datasets de un snapshot."""
    header = [
        "# Perfil de datasets",
        "",
        f"Snapshot `{snapshot_id}`. Generado por `rutagt-profile`; no editar a mano.",
        "",
    ]
    sections = [render_dataset(name, profile) for name, profile in profiles.items()]
    return "\n".join([*header, *sections])
